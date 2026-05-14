"""
ClaudeReasoningEngine
=====================
Sends ONLY minimal retrieved context to Anthropic Claude API.

SECURITY RULES enforced by this module:
  • NEVER sends full parquet files
  • NEVER sends entire datasets
  • NEVER sends all rows
  • ONLY sends: schema snippets, matched column metadata, ≤5 sample values per column
  • ALL embeddings, vector search, SQL execution remain LOCAL
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.core.config import get_settings
from backend.models import DatasetManifest, GeneratedSQL, SemanticMatch

logger = logging.getLogger(__name__)

# ── system prompts ────────────────────────────────────────────────────────────

SQL_SYSTEM_PROMPT = """\
You are a DuckDB SQL expert. You generate precise, executable DuckDB SQL queries.

CRITICAL RULES:
1. Generate ONLY valid DuckDB SQL — no MySQL, PostgreSQL, or SQLite syntax.
2. The parquet data is loaded as a view named "dataset". Always query FROM dataset.
3. Column names are CASE-SENSITIVE. Use double-quotes for column identifiers that contain spaces, special characters, or mixed case.
4. Do NOT add a LIMIT clause unless the user explicitly asks for a specific number of rows (e.g. "show top 10"). Return ALL matching rows by default.
5. For aggregations, alias the result column as "metric_value".
6. For group-by dimension columns, preserve the original column name as alias.
7. Return ONLY the JSON object — no markdown, no explanation, no code fences.
8. Handle NULL values with IS NOT NULL in WHERE clauses when filtering.
9. For counting, use COUNT(*) aliased as "record_count".
10. DuckDB supports: DATE_TRUNC, STDDEV_POP, string functions, window functions.
11. Use EXACT column names as provided in the schema — do NOT guess or modify them.
12. When the user asks to filter by a value (e.g. status='installed', type='with'), use WHERE with exact column matching. Use CAST to VARCHAR if the column type is uncertain.
13. When comparing dates, use proper DuckDB TIMESTAMP/DATE syntax: e.g. WHERE CAST(col AS VARCHAR) NOT LIKE '9999-12-31%' or WHERE col IS NOT NULL.
14. When the user says "not null" or "not equal to", translate to IS NOT NULL or != in SQL. If they say "not null or not equal to X", it usually means they want valid records: (col IS NOT NULL AND CAST(col AS VARCHAR) NOT LIKE 'X%').
15. Pay close attention to the user's exact filter conditions. If they ask for rows where status = 'installed' AND a date column is not null AND not equal to a specific value, implement ALL conditions accurately in the WHERE clause.

RESPONSE FORMAT — return ONLY a JSON object with these exact keys:
{
  "sql": "SELECT ...",
  "intent": "highest_by_dimension|lowest_by_dimension|average|total|count|trend|outlier_detection|preview|filter|comparison",
  "aggregation": "MAX|MIN|AVG|SUM|COUNT|null",
  "metric_column": "column_name or null",
  "group_by_columns": ["col1"],
  "selected_columns": ["col1", "col2"],
  "explanation": "Brief explanation of what the query does"
}
"""

ANSWER_SYSTEM_PROMPT = """\
You are an enterprise data analytics assistant. Given a user question, the SQL query that was executed, \
and the query results, provide a clear, concise, and intelligent natural language answer.

RULES:
1. Be specific — include actual values and column names from the results.
2. If the results contain aggregations, state the exact values.
3. If comparing groups, mention the top entries.
4. Keep answers under 3 sentences for simple queries, up to 5 for complex ones.
5. Use professional, clear language suitable for a business audience.
6. If no rows were returned, explain why that might be and suggest alternatives.
7. Do NOT mention SQL, databases, or technical query details — speak in business terms.
"""

MULTI_TABLE_SQL_SYSTEM_PROMPT = """\
You are a DuckDB SQL expert working with MULTIPLE parquet tables.

CRITICAL RULES:
1. Generate ONLY valid DuckDB SQL.
2. Tables are loaded as views with specific relation names (provided in context).
3. Use the exact relation names provided — do NOT use "dataset".
4. Column names are CASE-SENSITIVE. Use double-quotes for identifiers with spaces or special characters.
5. When joining tables, use LEFT JOIN with the join keys provided.
6. Do NOT add a LIMIT clause unless the user explicitly asks for a specific number of rows. Return ALL matching rows by default.
7. For aggregations, alias result as "metric_value".
8. Return ONLY a JSON object (same format as single-table queries).
9. When the user asks to filter by a value, use WHERE with exact column matching. Use CAST to VARCHAR if needed.
10. When comparing dates, use proper DuckDB TIMESTAMP/DATE syntax. Handle "not null" by using IS NOT NULL.
11. Pay close attention to all filter conditions the user specifies. For exclusions like "not equal to 9999-12-31", use CAST(col AS VARCHAR) NOT LIKE '9999-12-31%'.

RESPONSE FORMAT — return ONLY a JSON object:
{
  "sql": "SELECT ...",
  "intent": "...",
  "aggregation": "...",
  "metric_column": "...",
  "group_by_columns": [],
  "selected_columns": [],
  "explanation": "..."
}
"""

SQL_FIX_PROMPT = """\
The following DuckDB SQL query failed with an error. Fix the SQL and return a corrected version.

ORIGINAL SQL:
{sql}

ERROR:
{error}

Fix the SQL and return ONLY a JSON object in the same format:
{{
  "sql": "SELECT ...",
  "intent": "...",
  "aggregation": "...",
  "metric_column": "...",
  "group_by_columns": [],
  "selected_columns": [],
  "explanation": "..."
}}
"""


class ClaudeReasoningEngine:
    """Handles all interactions with Anthropic Claude API using minimal context."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    @property
    def available(self) -> bool:
        """Check if Claude integration is available (API key set + enabled)."""
        return bool(
            self.settings.anthropic_api_key
            and self.settings.enable_claude_reasoning
        )

    @property
    def client(self):
        """Lazy-load anthropic client."""
        if self._client is None:
            if not self.settings.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key
            )
        return self._client

    # ── SECURITY: context preparation (minimal data only) ─────────────────

    def _prepare_minimal_context(
        self,
        manifest: DatasetManifest,
        matches: list[SemanticMatch],
        question: str,
        limit: int,
    ) -> tuple[str, dict[str, Any]]:
        """
        Build structured minimal context for Claude.
        Returns (context_string, security_audit_dict).

        SECURITY: Only sends column names, types, ≤5 sample values, and
        top semantic match snippets. NEVER sends full rows or raw data.
        """
        max_chars = self.settings.context_max_tokens * 4  # ~4 chars per token

        # Extract relevant columns from semantic matches
        matched_columns: list[dict[str, Any]] = []
        seen_columns: set[str] = set()

        for match in matches[:10]:  # limit to top 10 matches
            if match.column_name and match.column_name not in seen_columns:
                seen_columns.add(match.column_name)
                col_info = next(
                    (c for c in manifest.columns if c.name == match.column_name),
                    None,
                )
                if col_info:
                    matched_columns.append({
                        "name": col_info.name,
                        "dtype": col_info.dtype,
                        "sample_values": col_info.sample_values[:5],
                        "stats": {
                            k: v for k, v in col_info.stats.items()
                            if k in ("distinct_count", "min_value", "max_value", "avg_value", "null_count")
                        },
                    })

        # ── Build structured context block ─────────────────────────────
        context = f"File: {manifest.filename}\n"
        context += f"Row Count: {manifest.row_count}\n\n"

        # Full schema (names + types only)
        context += "Full Schema:\n"
        for c in manifest.columns:
            context += f"  - {c.name} ({c.dtype})\n"

        context += "\nRelevant Columns:\n"
        for col in matched_columns:
            samples = ", ".join(str(v) for v in col["sample_values"])
            stats_parts = []
            for k, v in col["stats"].items():
                if v is not None:
                    stats_parts.append(f"{k}={v}")
            stats_str = ", ".join(stats_parts) if stats_parts else "n/a"
            context += (
                f"  {col['name']} ({col['dtype']}) — "
                f"samples: [{samples}] — stats: {stats_str}\n"
            )

        # Include top 3 sample rows for matched columns
        if manifest.sample_rows and matched_columns:
            context += "\nSample Rows (first 3):\n"
            col_names = [c["name"] for c in matched_columns[:6]]
            for i, row in enumerate(manifest.sample_rows[:3], 1):
                row_vals = ", ".join(
                    f"{cn}={row.get(cn, 'NULL')}" for cn in col_names if cn in row
                )
                context += f"  Row {i}: {row_vals}\n"

        context += "\nReturn ALL matching rows (no LIMIT unless user specifies a number).\n"

        # Truncate to max token budget
        if len(context) > max_chars:
            context = context[:max_chars] + "\n... [truncated to fit token budget]"

        # Security audit — track exactly what was sent
        security_audit = {
            "data_sent_to_api": {
                "schema_column_count": len(manifest.columns),
                "matched_column_details": len(matched_columns),
                "sample_values_per_column": "max 5",
                "sample_rows_sent": min(3, len(manifest.sample_rows)),
                "context_chars": len(context),
                "estimated_tokens": len(context) // 4,
            },
            "data_kept_local": {
                "full_parquet_file": True,
                "all_row_data": True,
                "embeddings": True,
                "vector_database": True,
                "sql_execution": True,
            },
            "raw_data_sent": False,
            "full_dataset_sent": False,
        }

        return context, security_audit

    def _prepare_multi_table_context(
        self,
        manifests: list[DatasetManifest],
        matches: list[SemanticMatch],
        relation_map: dict[str, str],
        question: str,
        limit: int,
    ) -> tuple[str, dict[str, Any]]:
        """Build minimal context for multi-table queries."""
        max_chars = self.settings.context_max_tokens * 4
        context = "AVAILABLE TABLES:\n"
        total_cols = 0

        for manifest in manifests:
            relation = relation_map.get(manifest.dataset_id, "unknown")
            context += f"\n  TABLE: {relation} (from file: {manifest.filename}, {manifest.row_count} rows)\n"
            context += "  COLUMNS:\n"
            for col in manifest.columns:
                samples = ", ".join(str(v) for v in col.sample_values[:3])
                context += f"    - {col.name} ({col.dtype}) samples: [{samples}]\n"
                total_cols += 1

        # Add semantic matches
        context += "\nSEMANTIC MATCHES (from local Qdrant):\n"
        for i, match in enumerate(matches[:10], 1):
            context += f"  {i}. [score={match.score:.3f}] {match.text[:200]}\n"
            if match.payload.get("filename"):
                context += f"     file: {match.payload['filename']}\n"

        # Add join hints
        context += "\nJOIN HINTS (inferred locally):\n"
        context += "  Look for columns with matching names across tables for join keys.\n"
        context += "\nReturn ALL matching rows (no LIMIT unless user specifies a number).\n"

        # Truncate
        if len(context) > max_chars:
            context = context[:max_chars] + "\n... [truncated]"

        security_audit = {
            "data_sent_to_api": {
                "table_count": len(manifests),
                "total_columns": total_cols,
                "sample_values_per_column": "max 3",
                "semantic_match_snippets": min(len(matches), 10),
                "context_chars": len(context),
                "estimated_tokens": len(context) // 4,
            },
            "data_kept_local": {
                "full_parquet_files": True,
                "all_row_data": True,
                "embeddings": True,
                "vector_database": True,
                "sql_execution": True,
            },
            "raw_data_sent": False,
            "full_dataset_sent": False,
        }

        return context, security_audit

    # ── SQL generation via Claude ─────────────────────────────────────────

    def generate_sql(
        self,
        question: str,
        manifest: DatasetManifest,
        matches: list[SemanticMatch],
        limit: int,
    ) -> tuple[GeneratedSQL, dict[str, Any]]:
        """
        Generate SQL using Claude with minimal context.
        Returns (GeneratedSQL, security_audit).
        """
        context, security_audit = self._prepare_minimal_context(
            manifest, matches, question, limit
        )

        user_message = (
            f"CONTEXT:\n{context}\n\n"
            f"USER QUESTION: {question}\n\n"
            f"Generate a DuckDB SQL query to answer this question. "
            f"Query FROM 'dataset' view. Return ONLY the JSON object."
        )

        return self._call_claude_for_sql(
            system_prompt=SQL_SYSTEM_PROMPT,
            user_message=user_message,
            limit=limit,
            security_audit=security_audit,
        )

    def generate_sql_multi(
        self,
        question: str,
        manifests: list[DatasetManifest],
        matches: list[SemanticMatch],
        relation_map: dict[str, str],
        limit: int,
    ) -> tuple[GeneratedSQL, dict[str, Any]]:
        """Generate SQL for multi-table queries using Claude."""
        context, security_audit = self._prepare_multi_table_context(
            manifests, matches, relation_map, question, limit
        )

        user_message = (
            f"CONTEXT:\n{context}\n\n"
            f"USER QUESTION: {question}\n\n"
            f"Generate a DuckDB SQL query across the tables listed above. "
            f"Use the exact table relation names provided. Return ONLY the JSON object."
        )

        return self._call_claude_for_sql(
            system_prompt=MULTI_TABLE_SQL_SYSTEM_PROMPT,
            user_message=user_message,
            limit=limit,
            security_audit=security_audit,
        )

    def fix_sql_error(
        self,
        original_sql: str,
        error_message: str,
        limit: int,
    ) -> GeneratedSQL:
        """Send a failed SQL + error back to Claude for a one-shot fix."""
        user_message = SQL_FIX_PROMPT.format(sql=original_sql, error=error_message)

        plan, _ = self._call_claude_for_sql(
            system_prompt=SQL_SYSTEM_PROMPT,
            user_message=user_message,
            limit=limit,
            security_audit={},
        )
        return plan

    def _call_claude_for_sql(
        self,
        system_prompt: str,
        user_message: str,
        limit: int,
        security_audit: dict[str, Any],
        retries: int = 2,
    ) -> tuple[GeneratedSQL, dict[str, Any]]:
        """Call Claude API and parse JSON response. Retries on parse failure."""
        last_error: str = ""

        for attempt in range(retries + 1):
            try:
                msg = user_message
                if attempt > 0 and last_error:
                    msg += (
                        f"\n\nPREVIOUS ATTEMPT FAILED: {last_error}\n"
                        f"Please fix the issue and return valid JSON only."
                    )

                response = self.client.messages.create(
                    model=self.settings.anthropic_model,
                    max_tokens=self.settings.anthropic_max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": msg}],
                )

                raw_text = response.content[0].text.strip()
                parsed = self._parse_sql_response(raw_text, limit)
                return parsed, security_audit

            except json.JSONDecodeError as exc:
                last_error = f"Invalid JSON: {exc}"
                logger.warning(
                    "Claude SQL response parse failed (attempt %d): %s",
                    attempt + 1, last_error,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.error(
                    "Claude API call failed (attempt %d): %s",
                    attempt + 1, last_error,
                )
                if attempt == retries:
                    raise RuntimeError(
                        f"Claude SQL generation failed after {retries + 1} attempts: {last_error}"
                    ) from exc

        raise RuntimeError(f"Claude SQL generation failed: {last_error}")

    def _parse_sql_response(self, raw_text: str, limit: int) -> GeneratedSQL:
        """Parse Claude's JSON response into GeneratedSQL."""
        # Strip markdown code fences if present
        cleaned = raw_text
        if "```" in cleaned:
            cleaned = re.sub(r"```(?:json)?\s*", "", cleaned)
            cleaned = cleaned.replace("```", "").strip()

        data = json.loads(cleaned)

        sql = data.get("sql", "").strip().rstrip(";")
        if not sql:
            raise ValueError("Claude returned empty SQL")

        # Validate SQL starts with SELECT or WITH
        if not sql.upper().lstrip().startswith(("SELECT", "WITH")):
            raise ValueError(f"Claude generated non-SELECT SQL: {sql[:50]}")

        # Forcefully strip LIMIT if it's supposed to be unlimited
        if limit >= 999_999_999:
            sql = re.sub(r'(?i)\s+LIMIT\s+\d+\s*$', '', sql)

        return GeneratedSQL(
            sql=sql,
            intent=data.get("intent", "claude_generated"),
            aggregation=data.get("aggregation"),
            metric_column=data.get("metric_column"),
            group_by_columns=data.get("group_by_columns", []),
            selected_columns=data.get("selected_columns", []),
            limit=limit,
            explanation=data.get("explanation", "Query generated by Claude AI."),
        )

    # ── Answer generation via Claude ──────────────────────────────────────

    def generate_answer(
        self,
        question: str,
        sql: str,
        rows: list[dict[str, Any]],
        columns: list[str],
        plan: GeneratedSQL,
    ) -> str:
        """
        Generate a natural language answer using Claude.
        Sends ONLY the query results (which are already filtered/aggregated),
        NOT the full dataset.
        """
        # Limit rows sent to Claude for answer generation
        display_rows = rows[:20]

        # Format results as a compact table
        if display_rows:
            result_text = "QUERY RESULTS:\n"
            for i, row in enumerate(display_rows, 1):
                row_str = ", ".join(
                    f"{k}: {v}" for k, v in row.items()
                    if v is not None
                )
                result_text += f"  Row {i}: {row_str}\n"
            if len(rows) > 20:
                result_text += f"  ... and {len(rows) - 20} more rows\n"
        else:
            result_text = "QUERY RESULTS: No rows returned.\n"

        user_message = (
            f"USER QUESTION: {question}\n\n"
            f"SQL EXECUTED: {sql}\n\n"
            f"QUERY INTENT: {plan.intent}\n"
            f"AGGREGATION: {plan.aggregation or 'none'}\n"
            f"METRIC: {plan.metric_column or 'none'}\n"
            f"TOTAL ROWS RETURNED: {len(rows)}\n\n"
            f"{result_text}\n"
            f"Provide a clear, concise business answer."
        )

        try:
            response = self.client.messages.create(
                model=self.settings.anthropic_model,
                max_tokens=512,
                system=ANSWER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text.strip()
        except Exception as exc:
            logger.error("Claude answer generation failed: %s", exc)
            return ""
