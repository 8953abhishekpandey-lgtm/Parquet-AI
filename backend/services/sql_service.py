"""
SQL Service — Orchestrates SQL generation with retry logic.

Manages the full SQL lifecycle:
1. Generate SQL from Claude
2. Validate SQL
3. Execute on DuckDB
4. If error → retry with error context (up to MAX_RETRIES)
"""

import os
import time
from typing import Any

from backend.anthropic_client.sql_generator import generate_sql, fix_sql
from backend.services.sql_validator import normalize_parquet_references, validate_sql
from backend.duckdb.executor import execute_sql, ExecutionResult

MAX_SQL_RETRIES = int(os.getenv("MAX_SQL_RETRIES", "3"))


class SQLAttempt:
    """Record of a single SQL generation/execution attempt."""

    def __init__(self, attempt_number: int, sql: str, error: str | None = None, time_ms: int = 0):
        self.attempt_number = attempt_number
        self.sql = sql
        self.error = error
        self.time_ms = time_ms

    def to_dict(self) -> dict:
        return {
            "attempt_number": self.attempt_number,
            "sql": self.sql,
            "error": self.error,
            "time_ms": self.time_ms,
        }


class SQLServiceResult:
    """Result of the full SQL generation + execution pipeline."""

    def __init__(
        self,
        success: bool,
        sql: str,
        execution_result: ExecutionResult | None,
        attempts: list[SQLAttempt],
        total_tokens: int,
        error: str | None = None,
    ):
        self.success = success
        self.sql = sql
        self.execution_result = execution_result
        self.attempts = attempts
        self.total_tokens = total_tokens
        self.error = error


async def generate_and_execute(
    context: str,
    user_question: str,
    on_step: Any = None,
) -> SQLServiceResult:
    """
    Generate SQL, validate, execute, and retry on failure.

    Args:
        context: Schema metadata context for Claude.
        user_question: The user's question.
        on_step: Optional async callback for progress updates.

    Returns:
        SQLServiceResult with the final SQL, results, and attempt history.
    """
    attempts: list[SQLAttempt] = []
    total_tokens = 0
    last_sql = ""
    last_error = ""

    for attempt_num in range(1, MAX_SQL_RETRIES + 1):
        start = time.time()

        try:
            # Step 1: Generate or fix SQL
            if attempt_num == 1 or not last_sql.strip():
                sql, tokens = generate_sql(
                    context,
                    user_question,
                    use_fallback=attempt_num > 1,
                )
            else:
                # Use fallback model on last attempt
                sql, tokens = fix_sql(
                    original_sql=last_sql,
                    error_message=last_error,
                    context=context,
                    attempt=attempt_num,
                )

            total_tokens += tokens
            sql = normalize_parquet_references(sql)
            last_sql = sql
            print(f"[SQL] Attempt {attempt_num} — Claude returned ({tokens} tokens):\n{sql[:200]}")

            # Step 2: Validate SQL
            validation = validate_sql(sql)
            if not validation.valid:
                elapsed = int((time.time() - start) * 1000)
                attempt = SQLAttempt(attempt_num, sql, validation.error, elapsed)
                attempts.append(attempt)
                last_error = validation.error or "Validation failed"

                if on_step:
                    await on_step(f"Attempt {attempt_num} validation failed: {validation.error}")
                continue

            # Step 3: Execute SQL
            result = execute_sql(sql)

            elapsed = int((time.time() - start) * 1000)

            if result.error:
                attempt = SQLAttempt(attempt_num, sql, result.error, elapsed)
                attempts.append(attempt)
                last_error = result.error

                if on_step:
                    await on_step(f"Attempt {attempt_num} execution error: {result.error}")
                continue

            if _should_retry_truncated_summary(user_question, sql, result):
                error_msg = (
                    "Grouped report returned too many rows and was truncated at the result cap. "
                    "Rewrite as a compact summary with fewer GROUP BY dimensions. "
                    "Do not group by unique IDs, meter IDs, raw GPS coordinates, exact timestamps, "
                    "or other high-cardinality fields unless explicitly requested. "
                    "For location reports, prefer utility office, area, region, district, or premise; "
                    "aggregate coordinates with AVG/MIN/MAX/ROUND."
                )
                attempt = SQLAttempt(attempt_num, sql, error_msg, elapsed)
                attempts.append(attempt)
                last_error = error_msg

                if on_step:
                    await on_step(f"Attempt {attempt_num} produced a truncated grouped report; retrying with coarser aggregation.")
                continue

            # Success!
            attempt = SQLAttempt(attempt_num, sql, None, elapsed)
            attempts.append(attempt)

            return SQLServiceResult(
                success=True,
                sql=sql,
                execution_result=result,
                attempts=attempts,
                total_tokens=total_tokens,
            )

        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            error_msg = str(e)
            attempt = SQLAttempt(attempt_num, last_sql, error_msg, elapsed)
            attempts.append(attempt)
            last_error = error_msg

            if on_step:
                await on_step(f"Attempt {attempt_num} error: {error_msg}")

    # All attempts failed
    return SQLServiceResult(
        success=False,
        sql=last_sql,
        execution_result=None,
        attempts=attempts,
        total_tokens=total_tokens,
        error=_build_failure_message(attempts),
    )


def _build_failure_message(attempts: list[SQLAttempt]) -> str:
    """Return the most helpful user-facing error for the attempt history."""
    model_errors = [
        attempt.error for attempt in attempts
        if attempt.error and _looks_like_model_not_found(attempt.error)
    ]
    if model_errors:
        return (
            "Claude rejected one of the configured model names. Check PRIMARY_MODEL "
            "and FALLBACK_MODEL in .env, then retry the question."
        )

    api_errors = [
        attempt.error for attempt in attempts
        if attempt.error and _looks_like_api_error(attempt.error)
    ]
    if api_errors and len(api_errors) == len(attempts):
        return (
            "Claude API failed before a valid SQL query could be generated. "
            "Check the API key, model names, and network/API status, then retry."
        )

    return (
        "I could not generate a valid query for this question after "
        f"{MAX_SQL_RETRIES} attempts. Please rephrase or check if "
        "the relevant columns exist in your uploaded files."
    )


def _looks_like_model_not_found(error: str) -> bool:
    error_lower = error.lower()
    return "not_found_error" in error_lower and "model" in error_lower


def _looks_like_api_error(error: str) -> bool:
    error_lower = error.lower()
    return (
        "error code:" in error_lower
        or "api" in error_lower
        or "anthropic" in error_lower
        or "request_id" in error_lower
    )


def _should_retry_truncated_summary(
    user_question: str,
    sql: str,
    result: ExecutionResult,
) -> bool:
    """Return whether a truncated grouped result should be regenerated more compactly."""
    if not result.truncated or "group by" not in sql.lower():
        return False

    question = user_question.lower()
    summary_terms = (
        "area",
        "basis",
        "breakdown",
        "by ",
        "group",
        "location",
        "report",
        "summary",
    )
    raw_terms = (
        "all data",
        "all rows",
        "every row",
        "list all",
        "raw",
        "show all",
    )
    return any(term in question for term in summary_terms) and not any(
        term in question for term in raw_terms
    )
