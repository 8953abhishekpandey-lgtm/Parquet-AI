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

CRITICAL — MANDATORY SYNTAX:
- You MUST use read_parquet('path') to reference files. NEVER use bare paths.
- CORRECT:   SELECT * FROM read_parquet('<absolute_filepath>.parquet')
- WRONG:     SELECT * FROM '<absolute_filepath>.parquet'
- WRONG:     SELECT * FROM <absolute_filepath>.parquet

STRICT RULES:
1. ALWAYS wrap file paths in read_parquet(): FROM read_parquet('path/to/file.parquet')
2. For multiple files use aliases: FROM read_parquet('f1.parquet') AS t1
3. For JOINs: JOIN read_parquet('f2.parquet') AS t2 ON t1.col = t2.col
4. Column names are CASE-SENSITIVE — use exactly as provided in schema
5. For string columns use ILIKE for case-insensitive filtering
6. Use RELATIONSHIP HINTS first for joins. Do not join generic ID columns across files unless a relationship hint says to.
7. Use all files needed to answer the question, but do not add unrelated files just because they exist.
8. For "by", "based on", "basis of", "group", "summary", "breakdown", or "count" questions,
   return a grouped report with GROUP BY and aggregate counts, not raw row-level data.
9. In grouped reports, do NOT select or GROUP BY unique row identifiers such as ID, Meter_ID,
   Utility_ID, ConsumerID, EquipmentId, or DeviceLocationId unless the user explicitly asks
   to list individual records or IDs. Use COUNT(DISTINCT ...) instead.
10. For grouped meter reports, summarize by useful dimensions such as consumer type,
    material/meter type, manufacturer, equipment status, HES, smart flag, channel count,
    and date ranges. Include COUNT(DISTINCT meter id) and COUNT(DISTINCT consumer id).
11. For area/location reports, group by business location fields such as area, region,
    utility office, premise, or rounded coordinates when available. Avoid grouping by
    unique device-location IDs unless the user explicitly asks for individual locations.
    Prefer the coarsest useful location column so the result is readable. If utility
    office/area/region exists, group by that before raw GPS. Do NOT GROUP BY exact
    GPS latitude/longitude unless the user asks for map points or exact coordinates;
    use AVG/MIN/MAX/ROUND for representative coordinates instead.
12. If a SELECT includes aggregate functions, every other selected expression must either
    be in GROUP BY or wrapped in a safe aggregate such as ANY_VALUE, MIN, MAX, COUNT,
    COUNT(DISTINCT ...), or STRING_AGG(DISTINCT ...).
13. For detail/report questions, avoid SELECT *. Select clear business columns and give every output column a unique alias.
14. Always include ORDER BY for ranking/grouped queries
15. Always include LIMIT only for top-N or raw detail queries, not for small grouped summaries
16. Handle NULLs: use COALESCE or IS NOT NULL where needed
17. For date columns use DATE '2024-01-01' format
18. Return ONLY the SQL query — no explanation, no markdown, no backticks
19. If a column is marked with "ALL values are literal string 'NULL' (no real data)",
    the column contains the TEXT 'NULL', not actual SQL NULLs. To find real values,
    filter with: WHERE col != 'NULL' AND col IS NOT NULL.
    For grouped reports, you MUST label this as 'Unknown / Not populated' with CASE instead of returning 'NULL'.
    Example: CASE WHEN c.Type = 'NULL' OR c.Type IS NULL THEN 'Unknown / Not populated' ELSE c.Type END AS consumer_type
    STILL generate a valid query — it may return 0 rows, which is a correct answer.
20. ALWAYS generate a valid SQL query. Never refuse. If data seems empty or
    columns seem to have no useful values, generate the query anyway —
    returning 0 rows is a valid and correct result.

SQL STYLE:
- For row-level detail questions like "meter details", "consumer meter list",
  "installed meters", or "show records", use the user's requested join/list style:
  SELECT explicit business columns with short table aliases, FROM the main entity,
  then JOIN related files using RELATIONSHIP HINTS.
- Use aliases derived from available filenames or entity roles, such as E, C, DL,
  DDL, CDL, MM, HM when those entities exist; otherwise use clear short aliases.
  Alias every output column when names could be ambiguous.
- Preserve the user's requested business columns when those columns exist in schema.
  For example, if the schema has meter number, material type, HES name, equipment id,
  consumer number, status, office/location, model, GPS, or account fields, include
  them for meter-detail questions.
- For single-file preview questions, SELECT * is allowed. For top-N questions,
  DuckDB syntax is SELECT * FROM ... LIMIT N, not SELECT TOP N.
- For status/date filters, preserve exact values from the user and use DuckDB
  TIMESTAMP/DATE literals or string comparisons that match the schema type.

DuckDB-specific syntax:
- String agg: STRING_AGG(col, ', ')
- Date parts: EXTRACT(YEAR FROM date_col)
- Type cast: col::INTEGER
- Regex: REGEXP_MATCHES(col, 'pattern')
"""

FIX_SQL_SYSTEM_PROMPT = """You are an expert DuckDB SQL debugger.
Fix the SQL query that caused the error below.
Return ONLY the corrected SQL query — no explanation, no markdown, no backticks.
Use exact column names and file paths from the schema.

DuckDB repair rules:
1. If the error is "column must appear in the GROUP BY clause", either add that
   expression to GROUP BY or wrap it in ANY_VALUE/MIN/MAX/STRING_AGG as appropriate.
2. For grouped reports, prefer fewer GROUP BY dimensions and aggregate detail columns.
3. Do not select unique IDs in grouped reports unless the user explicitly asked to list IDs.
4. If a column name is invalid, replace it with the exact available schema column.
5. Return a complete SQL query. Do not truncate GROUP BY, ORDER BY, or closing clauses."""


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
IMPORTANT: You MUST use read_parquet('filepath') syntax for every file reference.
Use the exact file paths and column names shown above.
Return ONLY the SQL query — no explanation."""

    model = FALLBACK_MODEL if use_fallback else PRIMARY_SQL_MODEL
    max_tokens = 2000 if use_fallback else 1400

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
If this is a GROUP BY/Binder error, make every selected non-aggregate expression
valid by either grouping it or aggregating it. For summary/report questions,
aggregate row-level detail fields instead of grouping by unique identifiers.
Return ONLY the corrected SQL query."""

    # Use fallback model on last attempt
    model = FALLBACK_MODEL if attempt >= 3 else PRIMARY_SQL_MODEL

    sql, tokens = call_claude(
        system_prompt=FIX_SQL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        max_tokens=1600,
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
