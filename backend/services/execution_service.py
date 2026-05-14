"""
Execution Service — High-level query execution orchestrator.

Coordinates the full query pipeline:
Schema loading → Join detection → Context building →
SQL generation → Validation → Execution → Answer generation
"""

import os
import time
from typing import Any

from backend.metadata.schema_store import SchemaStore
from backend.services.join_service import load_join_map
from backend.services.context_builder import build_sql_context, build_files_summary
from backend.services.sql_service import generate_and_execute
from backend.anthropic_client.answer_generator import generate_answer


async def execute_query(
    question: str,
    schema_store: SchemaStore,
    metadata_dir: str,
    selected_files: list[str] | None = None,
    on_step: Any = None,
) -> dict[str, Any]:
    """
    Execute a full text-to-SQL query pipeline.

    Args:
        question: User's natural language question.
        schema_store: SchemaStore instance for loading schemas.
        metadata_dir: Path to metadata directory.
        selected_files: Optional list of specific files to query.
        on_step: Optional async callback for progress updates.

    Returns:
        Complete query response dictionary.
    """
    pipeline_start = time.time()
    total_tokens = 0
    pipeline_steps = []

    def add_step(number: int, label: str, status: str, detail: str = "", time_ms: int = 0):
        pipeline_steps.append({
            "step_number": number,
            "label": label,
            "status": status,
            "detail": detail,
            "time_ms": time_ms,
        })

    # Step 1: Question received
    add_step(1, "Question received", "done", question[:100])

    # Step 2: Load schemas
    step_start = time.time()
    all_schemas = schema_store.get_all_schemas()
    if not all_schemas:
        add_step(2, "Loading schema metadata", "error", "No files uploaded")
        return {
            "question": question,
            "error": "No files uploaded. Please upload parquet files first.",
            "pipeline_steps": pipeline_steps,
        }

    files_summary = build_files_summary(all_schemas)
    add_step(2, "Loading schema metadata", "done", files_summary, int((time.time() - step_start) * 1000))

    # Step 3: Detect joins
    step_start = time.time()
    join_map = load_join_map(metadata_dir)
    join_detail = ""
    if join_map:
        join_cols = list(join_map.keys())[:3]
        join_detail = f"{', '.join(join_cols)} shared across files"
    else:
        join_detail = "No shared columns detected"
    add_step(3, "Detecting join opportunities", "done", join_detail, int((time.time() - step_start) * 1000))

    # Step 4: Build context
    step_start = time.time()
    context, token_count = build_sql_context(all_schemas, join_map, question, selected_files)
    add_step(4, "Building Claude context", "done", f"{token_count} tokens", int((time.time() - step_start) * 1000))

    # Step 5: Generate and execute SQL
    step_start = time.time()

    async def sql_step_callback(msg):
        if on_step:
            await on_step(msg)

    sql_result = await generate_and_execute(context, question, on_step=sql_step_callback)
    sql_time = int((time.time() - step_start) * 1000)
    total_tokens += sql_result.total_tokens

    if not sql_result.success:
        add_step(5, "Generating SQL (Claude)", "error", sql_result.error or "Failed", sql_time)
        return {
            "question": question,
            "sql": sql_result.sql,
            "error": sql_result.error,
            "sql_attempts": len(sql_result.attempts),
            "attempts_detail": [a.to_dict() for a in sql_result.attempts],
            "tokens_used": total_tokens,
            "pipeline_steps": pipeline_steps,
        }

    add_step(5, "Generating SQL (Claude)", "done",
             sql_result.sql[:80] + "..." if len(sql_result.sql) > 80 else sql_result.sql,
             sql_time)

    # Step 6: Validation (already done in sql_service)
    add_step(6, "Validating SQL", "done", "Passed all checks")

    # Step 7: DuckDB execution
    exec_result = sql_result.execution_result
    exec_detail = f"{exec_result.row_count} rows returned in {exec_result.execution_time_ms}ms"
    if exec_result.truncated:
        exec_detail += " (truncated)"
    add_step(7, "Executing on DuckDB", "done", exec_detail, exec_result.execution_time_ms)

    # Step 8: Generate answer
    step_start = time.time()
    files_queried = _extract_queried_files(sql_result.sql)

    try:
        answer, answer_tokens = generate_answer(
            user_question=question,
            results=exec_result.rows,
            columns=exec_result.columns,
        )
        total_tokens += answer_tokens
        add_step(8, "Generating answer (Claude)", "done", f"{answer_tokens} tokens", int((time.time() - step_start) * 1000))
    except Exception as e:
        answer = _fallback_answer(exec_result.rows, exec_result.columns)
        add_step(8, "Generating answer (Claude)", "error", str(e)[:80], int((time.time() - step_start) * 1000))

    # Step 9: Complete
    total_time = int((time.time() - pipeline_start) * 1000)
    add_step(9, "Complete", "done", f"Total: {total_time}ms")

    return {
        "question": question,
        "sql": sql_result.sql,
        "raw_results": exec_result.rows,
        "columns": exec_result.columns,
        "row_count": exec_result.row_count,
        "natural_language_answer": answer,
        "files_queried": files_queried,
        "execution_time_ms": total_time,
        "duckdb_time_ms": exec_result.execution_time_ms,
        "sql_attempts": len(sql_result.attempts),
        "attempts_detail": [a.to_dict() for a in sql_result.attempts],
        "tokens_used": total_tokens,
        "truncated": exec_result.truncated,
        "pipeline_steps": pipeline_steps,
        "context_tokens": token_count,
    }


def _extract_queried_files(sql: str) -> list[str]:
    """Extract filenames from read_parquet() calls in SQL."""
    import re
    paths = re.findall(r"read_parquet\s*\(\s*'([^']+)'\s*\)", sql)
    filenames = []
    for p in paths:
        name = os.path.basename(p)
        if name not in filenames:
            filenames.append(name)
    return filenames


def _fallback_answer(rows: list[dict], columns: list[str]) -> str:
    """Generate a simple fallback answer when Claude is unavailable."""
    if not rows:
        return "No data found matching your criteria."
    return f"Query returned **{len(rows)}** rows with columns: {', '.join(columns)}."
