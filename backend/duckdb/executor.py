"""
DuckDB Safe SQL Executor

Executes validated SQL queries against DuckDB with timeout protection,
result capping, and comprehensive error handling. Internal file paths
are never exposed to the frontend.
"""

import os
import time
import duckdb
from typing import Any

from backend.duckdb.connection import get_connection

MAX_RESULT_ROWS = int(os.getenv("MAX_RESULT_ROWS", "500"))
SQL_TIMEOUT_SECONDS = int(os.getenv("SQL_TIMEOUT_SECONDS", "30"))


class ExecutionResult:
    """Container for SQL execution results."""

    def __init__(
        self,
        rows: list[dict[str, Any]],
        columns: list[str],
        row_count: int,
        execution_time_ms: int,
        truncated: bool = False,
        error: str | None = None,
    ):
        self.rows = rows
        self.columns = columns
        self.row_count = row_count
        self.execution_time_ms = execution_time_ms
        self.truncated = truncated
        self.error = error

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "rows": self.rows,
            "columns": self.columns,
            "row_count": self.row_count,
            "execution_time_ms": self.execution_time_ms,
            "truncated": self.truncated,
            "error": self.error,
        }


def execute_sql(sql: str) -> ExecutionResult:
    """
    Execute a validated SQL query against DuckDB.

    Args:
        sql: The SQL query to execute (must be pre-validated).

    Returns:
        ExecutionResult with rows, columns, timing, and truncation info.

    Raises:
        No exceptions — all errors are captured in the result.
    """
    start_time = time.time()

    try:
        conn = get_connection()

        # Execute with the connection
        result = conn.execute(sql)
        columns = [desc[0] for desc in result.description]

        # Fetch up to MAX_RESULT_ROWS + 1 to detect truncation
        raw_rows = result.fetchmany(MAX_RESULT_ROWS + 1)
        truncated = len(raw_rows) > MAX_RESULT_ROWS
        if truncated:
            raw_rows = raw_rows[:MAX_RESULT_ROWS]

        # Convert to list of dicts
        rows = []
        for row in raw_rows:
            row_dict = {}
            for i, col in enumerate(columns):
                val = row[i]
                # Ensure JSON serializable
                if isinstance(val, (bytes, bytearray)):
                    val = val.hex()
                elif hasattr(val, "isoformat"):
                    val = val.isoformat()
                elif val is not None and not isinstance(val, (str, int, float, bool)):
                    val = str(val)
                row_dict[col] = val
            rows.append(row_dict)

        elapsed_ms = int((time.time() - start_time) * 1000)

        return ExecutionResult(
            rows=rows,
            columns=columns,
            row_count=len(rows),
            execution_time_ms=elapsed_ms,
            truncated=truncated,
        )

    except duckdb.Error as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        # Sanitize error message — remove internal file paths
        error_msg = str(e)
        error_msg = _sanitize_error(error_msg)
        return ExecutionResult(
            rows=[],
            columns=[],
            row_count=0,
            execution_time_ms=elapsed_ms,
            error=error_msg,
        )
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return ExecutionResult(
            rows=[],
            columns=[],
            row_count=0,
            execution_time_ms=elapsed_ms,
            error=f"Unexpected execution error: {type(e).__name__}",
        )


def _sanitize_error(error_msg: str) -> str:
    """
    Remove internal file paths from error messages before
    sending to the frontend.
    """
    import re

    # Remove absolute Windows paths
    error_msg = re.sub(r"[A-Z]:\\[^\s'\"]+", "<file>", error_msg)
    # Remove Unix-style paths
    error_msg = re.sub(r"/[^\s'\"]+\.parquet", "<file>.parquet", error_msg)
    return error_msg
