from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.core.config import get_settings
from backend.models import DatasetManifest, GeneratedSQL, SemanticMatch

logger = logging.getLogger(__name__)

SQL_SYSTEM_PROMPT = """\
You are a DuckDB SQL expert. You generate precise, executable DuckDB SQL queries.
Always use read_parquet('{absolute_filepath}') syntax.
For joins across files use:
  SELECT ... 
  FROM read_parquet('file1.parquet') t1
  JOIN read_parquet('file2.parquet') t2 ON t1.common_col = t2.common_col
Column names are case-sensitive.
For aggregations always include GROUP BY.
Support: SUM, AVG, COUNT, MAX, MIN, LIKE, WHERE, HAVING, ORDER BY, LIMIT.
If multiple files are relevant, always consider JOINs.
Return ONLY valid DuckDB SQL. No explanation. No markdown.
"""

ANSWER_SYSTEM_PROMPT = """\
You are a data analyst. Give a clear, concise, friendly answer.
Use bullet points for multiple values.
Bold the key numbers or names.
End with a one-line insight.
"""

MULTI_TABLE_SQL_SYSTEM_PROMPT = SQL_SYSTEM_PROMPT

SQL_FIX_PROMPT = """\
Fix this DuckDB SQL error: {error}
Original SQL: {sql}
Return ONLY valid DuckDB SQL. No explanation. No markdown.
"""

class ClaudeReasoningEngine:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    @property
    def available(self) -> bool:
        return bool(
            self.settings.anthropic_api_key
            and self.settings.enable_claude_reasoning
        )

    @property
    def client(self):
        if self._client is None:
            if not self.settings.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key
            )
        return self._client

    def _prepare_minimal_context(
        self,
        manifests: list[DatasetManifest],
        matches: list[SemanticMatch],
        question: str,
        limit: int,
        join_map: dict[str, list[str]] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        max_chars = self.settings.max_context_tokens * 4
        
        context_parts = []
        
        # 1. Retrieved column names + datatypes (always include)
        cols_text = "COLUMNS:\n"
        for match in matches[:20]:
            if match.column_name:
                filename = match.payload.get("filename", "")
                filepath = match.payload.get("file_path", "")
                dtype = match.payload.get("datatype", "unknown")
                cols_text += f"- {match.column_name} ({dtype}) in {filename} [{filepath}]\n"
        
        context_parts.append(cols_text)
        
        # 2. Sample values top 3 per column
        samples_text = "SAMPLES:\n"
        for match in matches[:20]:
            if match.column_name and "sample_values" in match.payload:
                samples = match.payload["sample_values"][:3]
                samples_text += f"- {match.column_name}: {', '.join(samples)}\n"
        context_parts.append(samples_text)
        
        # 3. Join map
        if len(manifests) > 1 and join_map:
            jm_text = "JOIN MAP:\n"
            for k, v in join_map.items():
                jm_text += f"- {k} present in: {', '.join(v)}\n"
            context_parts.append(jm_text)
            
        # 4. Top 2 sample rows
        rows_text = "SAMPLE ROWS:\n"
        for manifest in manifests:
            if manifest.sample_rows:
                for idx, row in enumerate(manifest.sample_rows[:2]):
                    rows_text += f"Row {idx} ({manifest.filename}): {row}\n"
        context_parts.append(rows_text)
        
        final_context = ""
        for part in context_parts:
            if len(final_context) + len(part) <= max_chars:
                final_context += part + "\n"
        
        security_audit = {
            "data_kept_local": {"sql_execution": True}
        }
        
        return final_context, security_audit

    def _call_claude_for_sql(self, system_prompt: str, user_message: str, max_tokens: int = 300) -> str:
        last_error = ""
        
        models_to_try = [
            self.settings.primary_model,
            self.settings.primary_model,
            self.settings.fallback_model
        ]
        
        for attempt, model in enumerate(models_to_try):
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
                
                raw_text = response.content[0].text.strip()
                if "```" in raw_text:
                    raw_text = re.sub(r"```(?:sql)?\s*", "", raw_text)
                    raw_text = raw_text.replace("```", "").strip()
                
                return raw_text
                
            except Exception as exc:
                last_error = str(exc)
                logger.error("Claude API call failed (attempt %d, model %s): %s", attempt + 1, model, last_error)
                
        raise RuntimeError(f"Claude SQL generation failed: {last_error}")

    def generate_sql(self, question: str, manifest: DatasetManifest, matches: list[SemanticMatch], limit: int) -> tuple[GeneratedSQL, dict[str, Any]]:
        context, security_audit = self._prepare_minimal_context([manifest], matches, question, limit)
        user_message = f"CONTEXT:\n{context}\n\nUSER QUESTION: {question}"
        
        sql = self._call_claude_for_sql(SQL_SYSTEM_PROMPT, user_message)
        
        return GeneratedSQL(sql=sql, intent="claude", limit=limit, explanation=""), security_audit

    def generate_sql_multi(self, question: str, manifests: list[DatasetManifest], matches: list[SemanticMatch], relation_map: dict[str, str], limit: int, join_map: dict[str, list[str]] = None) -> tuple[GeneratedSQL, dict[str, Any]]:
        context, security_audit = self._prepare_minimal_context(manifests, matches, question, limit, join_map=join_map)
        user_message = f"CONTEXT:\n{context}\n\nUSER QUESTION: {question}"
        
        sql = self._call_claude_for_sql(MULTI_TABLE_SQL_SYSTEM_PROMPT, user_message)
        
        return GeneratedSQL(sql=sql, intent="claude", limit=limit, explanation=""), security_audit

    def fix_sql_error(self, original_sql: str, error_message: str, limit: int) -> GeneratedSQL:
        user_message = SQL_FIX_PROMPT.format(sql=original_sql, error=error_message)
        sql = self._call_claude_for_sql(SQL_SYSTEM_PROMPT, user_message)
        return GeneratedSQL(sql=sql, intent="claude_fix", limit=limit, explanation="")

    def generate_answer(self, question: str, sql: str, rows: list[dict[str, Any]], columns: list[str], plan: GeneratedSQL) -> str:
        display_rows = rows[:10]
        result_text = json.dumps(display_rows)
        
        user_message = f"Question: {question}\nSQL Results: {result_text}\nAnswer in 3-5 sentences max."
        
        try:
            response = self.client.messages.create(
                model=self.settings.primary_model,
                max_tokens=400,
                system=ANSWER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text.strip()
        except Exception as exc:
            logger.error("Claude answer generation failed: %s", exc)
            return ""
