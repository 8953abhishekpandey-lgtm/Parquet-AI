"""
SQL Generator — Claude-powered DuckDB SQL generation.

Generates precise DuckDB SQL from natural language questions
using schema metadata context. Only schema metadata (column names,
types, sample values) is sent to Claude — never raw data.
"""

from backend.anthropic_client.client import (
    call_claude,
    PRIMARY_SQL_MODEL,
    FALLBACK_MODEL,
)

SQL_SYSTEM_PROMPT = """You are an expert DuckDB SQL analyst.

STRICT RULES:
1. Always use read_parquet('absolute/path/to/file.parquet') syntax
2. For multiple files use aliases: FROM read_parquet('f1.parquet') AS t1
3. For JOINs: JOIN read_parquet('f2.parquet') AS t2 ON t1.col = t2.col
4. Column names are CASE-SENSITIVE — use exactly as provided in schema
5. For string columns use ILIKE for case-insensitive filtering
6. Always include ORDER BY for ranking queries
7. Always include LIMIT for top-N queries
8. Handle NULLs: use COALESCE or IS NOT NULL where needed
9. For date columns use DATE '2024-01-01' format
10. Return ONLY the SQL query — no explanation, no markdown, no backticks

DuckDB-specific syntax:
- String agg: STRING_AGG(col, ', ')
- Date parts: EXTRACT(YEAR FROM date_col)
- Type cast: col::INTEGER
- Regex: REGEXP_MATCHES(col, 'pattern')
"""

FIX_SQL_SYSTEM_PROMPT = """You are an expert DuckDB SQL debugger.
Fix the SQL query that caused the error below.
Return ONLY the corrected SQL query — no explanation, no markdown, no backticks.
Use exact column names and file paths from the schema."""


def generate_sql(context: str, user_question: str, use_fallback: bool = False) -> tuple[str, int]:
    """
    Generate a DuckDB SQL query from a natural language question.

    Args:
        context: Schema metadata context built by context_builder.
        user_question: The user's natural language question.
        use_fallback: Whether to use the fallback (stronger) model.

    Returns:
        Tuple of (sql_query, tokens_used).
    """
    user_prompt = f"""{context}

User Question: {user_question}

Generate a single DuckDB SQL query that answers this question.
Use the exact file paths and column names shown above.
Return ONLY the SQL query."""

    model = FALLBACK_MODEL if use_fallback else PRIMARY_SQL_MODEL
    max_tokens = 1000 if use_fallback else 500

    sql, tokens = call_claude(
        system_prompt=SQL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=0.0,
    )

    # Clean up any residual markdown formatting
    sql = _clean_sql(sql)
    return sql, tokens


def fix_sql(
    original_sql: str,
    error_message: str,
    context: str,
    attempt: int = 2,
) -> tuple[str, int]:
    """
    Ask Claude to fix a SQL query that produced an error.

    Args:
        original_sql: The SQL that failed.
        error_message: The DuckDB error message.
        context: Schema metadata context.
        attempt: Current retry attempt number.

    Returns:
        Tuple of (fixed_sql, tokens_used).
    """
    urgency = ""
    if attempt >= 3:
        urgency = (
            "\nThis is the FINAL attempt. Be extremely careful with column names, "
            "data types, and file paths. Double-check everything."
        )

    user_prompt = f"""Fix this DuckDB error:

Error: {error_message}

Original SQL:
{original_sql}

Schema:
{context}
{urgency}
Return ONLY the corrected SQL query."""

    # Use fallback model on last attempt
    model = FALLBACK_MODEL if attempt >= 3 else PRIMARY_SQL_MODEL

    sql, tokens = call_claude(
        system_prompt=FIX_SQL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=500,
        temperature=0.0,
    )

    sql = _clean_sql(sql)
    return sql, tokens


def _clean_sql(sql: str) -> str:
    """Remove markdown code fences and extra whitespace from SQL."""
    sql = sql.strip()
    # Remove ```sql ... ``` wrappers
    if sql.startswith("```"):
        lines = sql.split("\n")
        # Remove first line (```sql) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        sql = "\n".join(lines).strip()
    # Remove inline backticks
    if sql.startswith("`") and sql.endswith("`"):
        sql = sql[1:-1].strip()
    return sql
