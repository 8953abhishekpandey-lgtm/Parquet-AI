"""
Context Builder — Build minimal Claude context from schema metadata.

Constructs a concise, token-efficient context string containing:
- File names and paths
- Column names and types
- Sample values (max 3 per column)
- Join opportunities

Strict token budget: MAX_CONTEXT_TOKENS (default 1500).
"""

import os
from typing import Any

MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "1500"))


def build_sql_context(
    all_schemas: list[dict[str, Any]],
    join_map: dict[str, list[str]],
    user_question: str,
    selected_files: list[str] | None = None,
) -> tuple[str, int]:
    """
    Build a minimal context string for Claude SQL generation.

    Args:
        all_schemas: List of schema dictionaries for all files.
        join_map: Detected join column map.
        user_question: The user's question (for context).
        selected_files: Optional list of filenames to filter to.

    Returns:
        Tuple of (context_string, estimated_token_count).
    """
    context = "=== AVAILABLE DATA FILES ===\n\n"

    schemas_to_use = all_schemas
    if selected_files:
        schemas_to_use = [
            s for s in all_schemas
            if s["filename"] in selected_files
        ]

    for schema in schemas_to_use:
        context += f"File: {schema['filename']}\n"
        context += f"Path: {schema['filepath']}\n"
        context += f"Rows: {schema['row_count']:,}\n"
        context += f"Columns:\n"

        for col in schema.get("columns", []):
            samples = col.get("sample_values", [])[:3]
            samples_str = str(samples) if samples else "[]"

            line = (
                f"  - {col['name']} ({col['dtype']})"
                f" | nulls: {col.get('null_pct', 0)}%"
                f" | samples: {samples_str}"
            )

            # Add min/max for numeric columns
            if col.get("min") is not None:
                line += f" | range: [{col['min']}, {col['max']}]"

            context += line + "\n"

        context += "\n"

    # Add join map
    if join_map:
        context += "=== POSSIBLE JOIN COLUMNS ===\n"
        for col, file_list in join_map.items():
            # Only show joins relevant to selected files
            if selected_files:
                relevant_files = [f for f in file_list if f in selected_files]
                if len(relevant_files) < 2:
                    continue
                context += f"  {col}: shared across {relevant_files}\n"
            else:
                context += f"  {col}: shared across {file_list}\n"
        context += "\n"

    # Estimate token count (rough: ~4 chars per token)
    estimated_tokens = len(context) // 4

    # Trim if over budget — remove sample values first
    if estimated_tokens > MAX_CONTEXT_TOKENS:
        context = _trim_context(all_schemas, join_map, selected_files)
        estimated_tokens = len(context) // 4

    return context, estimated_tokens


def _trim_context(
    all_schemas: list[dict],
    join_map: dict[str, list[str]],
    selected_files: list[str] | None = None,
) -> str:
    """Build a trimmed context without sample values."""
    context = "=== AVAILABLE DATA FILES ===\n\n"

    schemas_to_use = all_schemas
    if selected_files:
        schemas_to_use = [
            s for s in all_schemas if s["filename"] in selected_files
        ]

    for schema in schemas_to_use:
        context += f"File: {schema['filename']}\n"
        context += f"Path: {schema['filepath']}\n"
        context += f"Rows: {schema['row_count']:,}\n"
        context += f"Columns:\n"

        for col in schema.get("columns", []):
            context += f"  - {col['name']} ({col['dtype']})\n"

        context += "\n"

    if join_map:
        context += "=== POSSIBLE JOIN COLUMNS ===\n"
        for col, file_list in join_map.items():
            context += f"  {col}: shared across {file_list}\n"

    return context


def build_files_summary(all_schemas: list[dict]) -> str:
    """
    Build a short summary of available files.

    Returns:
        Human-readable summary string.
    """
    if not all_schemas:
        return "No files loaded"

    total_files = len(all_schemas)
    total_cols = sum(s.get("col_count", 0) for s in all_schemas)
    total_rows = sum(s.get("row_count", 0) for s in all_schemas)

    return f"{total_files} files · {total_cols} columns · {total_rows:,} total rows"
