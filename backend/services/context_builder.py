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
import re
from typing import Any

MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "1500"))
MAX_RELATIONSHIP_HINTS = int(os.getenv("MAX_RELATIONSHIP_HINTS", "12"))


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
        context += f"Path: {_sql_safe_path(schema['filepath'])}\n"
        context += f"Rows: {schema['row_count']:,}\n"
        context += f"Columns:\n"

        for col in schema.get("columns", []):
            samples = col.get("sample_values", [])[:3]
            samples_str = str(samples) if samples else "[]"

            # Detect columns that only contain the literal string "NULL"
            all_null_string = (
                col.get("unique_count", 0) == 1
                and len(samples) == 1
                and samples[0] == "NULL"
            )

            line = (
                f"  - {col['name']} ({col['dtype']})"
                f" | nulls: {col.get('null_pct', 0)}%"
                f" | samples: {samples_str}"
            )

            if all_null_string:
                line += " | ⚠ ALL values are literal string 'NULL' (no real data)"

            # Add min/max for numeric columns
            if col.get("min") is not None:
                line += f" | range: [{col['min']}, {col['max']}]"

            context += line + "\n"

        context += "\n"

    # Add join map
    if join_map:
        context += "=== POSSIBLE JOIN COLUMNS ===\n"
        context += "These are same-name column candidates only. Prefer RELATIONSHIP HINTS below for business joins.\n"
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

    relationship_hints = _build_relationship_hints(schemas_to_use)
    if relationship_hints:
        context += "=== RELATIONSHIP HINTS ===\n"
        context += (
            "Inferred from column names, uniqueness, samples, and ranges. "
            "Use these joins before same-name candidates. Do NOT join generic ID columns across files unless listed here.\n"
        )
        for hint in relationship_hints:
            context += f"  - {hint}\n"
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
        context += f"Path: {_sql_safe_path(schema['filepath'])}\n"
        context += f"Rows: {schema['row_count']:,}\n"
        context += f"Columns:\n"

        for col in schema.get("columns", []):
            context += f"  - {col['name']} ({col['dtype']})\n"

        context += "\n"

    if join_map:
        context += "=== POSSIBLE JOIN COLUMNS ===\n"
        context += "These are same-name column candidates only. Prefer RELATIONSHIP HINTS below for business joins.\n"
        for col, file_list in join_map.items():
            context += f"  {col}: shared across {file_list}\n"

    relationship_hints = _build_relationship_hints(schemas_to_use)
    if relationship_hints:
        context += "\n=== RELATIONSHIP HINTS ===\n"
        context += (
            "Inferred from column names, uniqueness, samples, and ranges. "
            "Use these joins before same-name candidates. Do NOT join generic ID columns across files unless listed here.\n"
        )
        for hint in relationship_hints:
            context += f"  - {hint}\n"

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


def _sql_safe_path(filepath: str) -> str:
    """Use slash-normalized paths so Claude emits DuckDB-friendly SQL strings."""
    return filepath.replace("\\", "/")


def _build_relationship_hints(schemas: list[dict]) -> list[str]:
    """Infer high-confidence cross-file relationships without hardcoded schema names."""
    columns = _flatten_columns(schemas)
    candidates: dict[tuple[str, str, str, str], tuple[float, str]] = {}

    for left in columns:
        for right in columns:
            if left["filename"] == right["filename"]:
                continue

            score, reasons = _relationship_score(left, right)
            if score < 8:
                continue

            key = tuple(sorted([
                f"{left['filename']}.{left['name']}",
                f"{right['filename']}.{right['name']}",
            ]))
            relationship = f"{left['filename']}.{left['name']} = {right['filename']}.{right['name']}"

            if key not in candidates or score > candidates[key][0]:
                candidates[key] = (score, relationship)

    ranked = sorted(candidates.values(), key=lambda item: item[0], reverse=True)
    return [relationship for _, relationship in ranked[:MAX_RELATIONSHIP_HINTS]]


def _flatten_columns(schemas: list[dict]) -> list[dict[str, Any]]:
    """Flatten schema columns with file-level metadata used by relationship scoring."""
    flattened: list[dict[str, Any]] = []
    for schema in schemas:
        filename = schema.get("filename", "")
        row_count = int(schema.get("row_count") or 0)
        file_tokens = set(_name_tokens(os.path.splitext(filename)[0]))
        for col in schema.get("columns", []):
            name = col.get("name", "")
            flattened.append({
                **col,
                "filename": filename,
                "row_count": row_count,
                "file_tokens": file_tokens,
                "name_tokens": set(_name_tokens(name)),
                "norm_name": _normalize_name(name),
            })
    return flattened


def _relationship_score(left: dict[str, Any], right: dict[str, Any]) -> tuple[float, list[str]]:
    """Score whether two columns likely form a safe join relationship."""
    if not _types_compatible(left.get("dtype", ""), right.get("dtype", "")):
        return 0, []

    left_name = left["norm_name"]
    right_name = right["norm_name"]
    if left_name == "id" and right_name == "id":
        return 0, []

    score = 0.0
    reasons: list[str] = []

    if left_name == right_name and left_name not in _generic_column_names():
        score += 5
        reasons.append("same column name")

    right_key_like = _is_key_like(right)
    if right_key_like:
        score += 3
        reasons.append(f"{right['filename']}.{right['name']} is key-like")

    mentions_file = right_key_like and _foreign_key_mentions_file(left, right)
    if mentions_file:
        score += 6
        reasons.append("foreign-key name matches file")

    if _foreign_key_mentions_column(left, right):
        score += 1
        reasons.append("foreign-key name matches column")

    sample_overlap = _sample_overlap(left, right)
    if sample_overlap:
        score += 4 + min(sample_overlap, 3)
        reasons.append("sample values overlap")

    range_overlap = _numeric_ranges_overlap(left, right)
    if range_overlap:
        score += 1
        reasons.append("numeric ranges overlap")

    generic_id_target = right_name == "id" and mentions_file
    if (left_name in _generic_column_names() or right_name in _generic_column_names()) and not generic_id_target:
        score -= 3

    if generic_id_target and not sample_overlap and not range_overlap:
        score -= 4

    if not mentions_file and left_name != right_name:
        score -= 4

    if not sample_overlap and not mentions_file and _looks_like_foreign_key(left) and _looks_like_foreign_key(right):
        score -= 4

    return score, reasons


def _name_tokens(name: str) -> list[str]:
    """Tokenize snake_case, PascalCase, and acronym-heavy names consistently."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    raw_tokens = re.split(r"[^A-Za-z0-9]+", spaced)
    tokens = [_normalize_token(token) for token in raw_tokens if token]
    return [token for token in tokens if token and token not in {"the", "a", "an"}]


def _normalize_name(name: str) -> str:
    """Normalize a column or file name for safe comparisons."""
    return "".join(_name_tokens(name))


def _normalize_token(token: str) -> str:
    """Normalize common identifier abbreviations without dataset-specific names."""
    normalized = token.lower()
    return {
        "dev": "device",
        "loc": "location",
        "cd": "code",
        "desc": "description",
    }.get(normalized, normalized)


def _types_compatible(left_dtype: str, right_dtype: str) -> bool:
    """Return whether two schema dtypes are safe to compare in a join."""
    left = _dtype_family(left_dtype)
    right = _dtype_family(right_dtype)
    return left == right or {left, right} <= {"integer", "float"}


def _dtype_family(dtype: str) -> str:
    """Map DuckDB/Arrow dtype strings into broad comparable families."""
    upper = dtype.upper()
    if any(token in upper for token in ("INT", "BIGINT", "SMALLINT", "TINYINT", "UBIGINT")):
        return "integer"
    if any(token in upper for token in ("DOUBLE", "FLOAT", "REAL", "DECIMAL", "NUMERIC")):
        return "float"
    if any(token in upper for token in ("DATE", "TIME")):
        return "datetime"
    if "BOOL" in upper:
        return "boolean"
    return "string"


def _is_key_like(col: dict[str, Any]) -> bool:
    """Return whether a column looks like a primary/natural key for its file."""
    if _is_link_file(col):
        return False

    row_count = max(int(col.get("row_count") or 0), 1)
    unique_count = int(col.get("unique_count") or 0)
    unique_ratio = unique_count / row_count
    name = col["norm_name"]
    return (
        name == "id"
        or name.endswith("id")
        or name.endswith("key")
        or name.endswith("code")
    ) and unique_ratio >= 0.8


def _foreign_key_mentions_file(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return whether a source column name references the target file entity."""
    if not _looks_like_foreign_key(left):
        return False
    target_tokens = right["file_tokens"] - {"bridge", "junction", "link", "map", "master", "table", "xref"}
    return bool(target_tokens) and target_tokens.issubset(left["name_tokens"])


def _foreign_key_mentions_column(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return whether a source column contains the target column identifier."""
    if not _looks_like_foreign_key(left):
        return False
    right_tokens = right["name_tokens"] - {"id", "key", "code"}
    if not right_tokens:
        return False
    return bool(left["name_tokens"] & right_tokens)


def _looks_like_foreign_key(col: dict[str, Any]) -> bool:
    """Return whether a column name looks like a foreign key."""
    name = col["norm_name"]
    return (
        name != "id"
        and (
            name.endswith("id")
            or name.endswith("key")
            or name.endswith("code")
            or "id" in col["name_tokens"]
        )
    )


def _sample_overlap(left: dict[str, Any], right: dict[str, Any]) -> int:
    """Count overlapping non-empty sample values between two columns."""
    left_values = {_sample_key(value) for value in left.get("sample_values", [])}
    right_values = {_sample_key(value) for value in right.get("sample_values", [])}
    ignored = {"", "null", "none", "nan"}
    left_values -= ignored
    right_values -= ignored
    return len(left_values & right_values)


def _sample_key(value: Any) -> str:
    """Normalize sample values for overlap checks."""
    if value is None:
        return ""
    return str(value).strip().lower()


def _numeric_ranges_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return whether two numeric columns have overlapping min/max ranges."""
    try:
        left_min = float(left.get("min"))
        left_max = float(left.get("max"))
        right_min = float(right.get("min"))
        right_max = float(right.get("max"))
    except (TypeError, ValueError):
        return False
    return max(left_min, right_min) <= min(left_max, right_max)


def _generic_column_names() -> set[str]:
    """Column names that are too generic to be trusted as relationship hints alone."""
    return {
        "id",
        "type",
        "status",
        "description",
        "createdby",
        "createdon",
        "compid",
        "changedby",
        "changedon",
        "devicetype",
        "insertedby",
        "inserteddate",
        "isactive",
        "datasource",
        "validfromdate",
        "validtodate",
    }


def _is_link_file(col: dict[str, Any]) -> bool:
    """Return whether a column belongs to a bridge/link-style table."""
    return bool(col["file_tokens"] & {"bridge", "junction", "link", "map", "xref"})
