"""
SQL Validator — Validates generated SQL before execution.

Performs multiple safety and correctness checks:
1. SQLGlot syntax parsing
2. File path existence verification
3. Dangerous operation blocking (DROP, DELETE, INSERT, etc.)
4. Ensures at least one read_parquet() reference exists
"""

import os
import re
from typing import Any


# Dangerous SQL operations that should never be executed
DANGEROUS_OPERATIONS = {
    "DROP", "DELETE", "INSERT", "UPDATE", "CREATE", "ALTER",
    "TRUNCATE", "COPY", "EXPORT", "ATTACH", "DETACH",
    "GRANT", "REVOKE", "EXECUTE",
}


class ValidationResult:
    """Container for SQL validation results."""

    def __init__(self, valid: bool, error: str | None = None, warnings: list[str] | None = None):
        self.valid = valid
        self.error = error
        self.warnings = warnings or []

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "error": self.error,
            "warnings": self.warnings,
        }


def normalize_parquet_references(sql: str) -> str:
    """
    Normalize common DuckDB parquet shorthand into the required read_parquet() form.

    DuckDB accepts FROM 'file.parquet', but the rest of this application expects
    explicit read_parquet() calls so validation, file extraction, and debug output
    all use the same shape.
    """
    if not sql:
        return sql

    normalized = re.sub(
        r"read_parquet\s*\(\s*\"([^\"]+?\.parquet)\"\s*\)",
        lambda match: f"read_parquet('{match.group(1)}')",
        sql,
        flags=re.IGNORECASE,
    )

    bare_parquet_ref = re.compile(
        r"\b(FROM|JOIN)\s+(['\"])([^'\"]+?\.parquet)\2",
        flags=re.IGNORECASE,
    )

    return bare_parquet_ref.sub(
        lambda match: f"{match.group(1)} read_parquet('{match.group(3)}')",
        normalized,
    )


def validate_sql(sql: str) -> ValidationResult:
    """
    Validate a SQL query for safety and correctness.

    Args:
        sql: The SQL query to validate.

    Returns:
        ValidationResult with validity status and any errors.
    """
    if not sql or not sql.strip():
        return ValidationResult(False, "Empty SQL query")

    sql_clean = sql.strip()
    warnings = []

    # Check 1: Block dangerous operations
    sql_upper = sql_clean.upper()
    for op in DANGEROUS_OPERATIONS:
        # Match as whole word to avoid false positives
        pattern = r'\b' + op + r'\b'
        if re.search(pattern, sql_upper):
            return ValidationResult(
                False,
                f"Dangerous operation detected: {op}. Only SELECT queries are allowed."
            )

    # Check 2: Must contain read_parquet
    if "read_parquet" not in sql_clean.lower():
        return ValidationResult(
            False,
            "Query must reference at least one parquet file using read_parquet()."
        )

    # Check 3: Must start with SELECT (or WITH for CTEs)
    first_word = sql_upper.lstrip().split()[0] if sql_upper.strip() else ""
    if first_word not in ("SELECT", "WITH"):
        return ValidationResult(
            False,
            f"Only SELECT queries are allowed. Found: {first_word}"
        )

    # Check 4: Verify referenced file paths exist
    file_paths = re.findall(r"read_parquet\s*\(\s*'([^']+)'\s*\)", sql_clean)
    missing_files = []
    for fpath in file_paths:
        if not os.path.exists(fpath):
            missing_files.append(fpath)

    if missing_files:
        return ValidationResult(
            False,
            f"Referenced files not found: {', '.join(missing_files)}"
        )

    # Check 5: Try SQLGlot parsing (best-effort)
    try:
        import sqlglot
        parsed = sqlglot.parse(sql_clean, read="duckdb")
        if not parsed:
            warnings.append("SQLGlot could not parse the query — proceeding anyway.")
    except ImportError:
        warnings.append("SQLGlot not available for syntax validation.")
    except Exception as e:
        # SQLGlot parse errors are warnings, not blockers
        # DuckDB SQL may have syntax SQLGlot doesn't understand
        warnings.append(f"SQLGlot parse warning: {str(e)[:100]}")

    return ValidationResult(True, None, warnings)
