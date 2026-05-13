from __future__ import annotations

from typing import Any

from backend.core.config import get_settings
from backend.models import DatasetManifest, GeneratedSQL, SemanticMatch


def build_minimal_rag_context(
    *,
    question: str,
    manifests: list[DatasetManifest],
    matches: list[SemanticMatch],
    limit: int,
    relation_map: dict[str, str] | None = None,
    candidate_plan: GeneratedSQL | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    manifest_by_id = {manifest.dataset_id: manifest for manifest in manifests}
    context_matches = matches[: settings.anthropic_context_match_limit]

    relevant_keys = _matched_column_keys(context_matches, manifest_by_id)
    if not relevant_keys:
        relevant_keys = _fallback_column_keys(manifests)

    relation_items = []
    for index, manifest in enumerate(manifests):
        relation_name = relation_map.get(manifest.dataset_id) if relation_map else "dataset"
        relation_items.append(
            {
                "dataset_id": manifest.dataset_id,
                "filename": manifest.filename,
                "relation_name": relation_name or f"dataset_{index}",
                "row_count": manifest.row_count,
            }
        )

    columns = []
    for dataset_id, column_name in relevant_keys:
        manifest = manifest_by_id.get(dataset_id)
        if manifest is None:
            continue
        column = next((item for item in manifest.columns if item.name == column_name), None)
        if column is None:
            continue
        columns.append(
            {
                "dataset_id": dataset_id,
                "filename": manifest.filename,
                "relation_name": (relation_map or {}).get(dataset_id, "dataset"),
                "column_name": column.name,
                "quoted_column_hint": f'"{column.name}"',
                "data_type": column.dtype,
                "semantic_label": column.normalized_name,
                "nullable": column.nullable,
                "sample_values": _limited_values(column.sample_values, settings.anthropic_sample_value_limit),
                "stats": _safe_stats(column.stats),
            }
        )

    sample_rows = _limited_sample_rows(context_matches, relevant_keys)
    retrieved_matches = []
    for match in context_matches:
        payload = match.payload or {}
        retrieved_matches.append(
            {
                "score": round(match.score, 6),
                "kind": match.kind,
                "dataset_id": payload.get("dataset_id"),
                "filename": payload.get("filename"),
                "document_id": payload.get("document_id"),
                "column_name": match.column_name,
                "text": _shorten(match.text, 700),
            }
        )

    return {
        "security_policy": {
            "raw_parquet_sent_to_llm": False,
            "full_dataset_sent_to_llm": False,
            "embeddings_location": "local sentence-transformers",
            "vector_db_location": "local Qdrant",
            "sql_execution_location": "local DuckDB",
            "llm_receives": "Only retrieved schema metadata, limited sample values, generated SQL, and tiny result previews.",
        },
        "question": question,
        "requested_limit": limit,
        "allowed_relations": relation_items,
        "relevant_columns": columns,
        "retrieved_matches": retrieved_matches,
        "limited_sample_rows": sample_rows,
        "local_candidate_sql": candidate_plan.sql if candidate_plan else None,
        "local_candidate_explanation": candidate_plan.explanation if candidate_plan else None,
        "context_counts": {
            "retrieved_match_count": len(retrieved_matches),
            "relevant_column_count": len(columns),
            "sample_row_count": len(sample_rows),
        },
    }


def build_result_context(
    *,
    question: str,
    plan: GeneratedSQL,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    settings = get_settings()
    preview_rows = rows[: settings.anthropic_result_row_limit]
    return {
        "security_policy": {
            "raw_parquet_sent_to_llm": False,
            "full_dataset_sent_to_llm": False,
            "result_rows_sent_to_llm": len(preview_rows),
            "sql_execution_location": "local DuckDB",
        },
        "question": question,
        "generated_sql": plan.sql,
        "sql_intent": plan.intent,
        "sql_explanation": plan.explanation,
        "columns": columns,
        "returned_row_count": len(rows),
        "rows_preview": preview_rows,
    }


def _matched_column_keys(
    matches: list[SemanticMatch],
    manifests: dict[str, DatasetManifest],
) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    keys: list[tuple[str, str]] = []
    for match in matches:
        dataset_id = str(match.payload.get("dataset_id", ""))
        if not dataset_id or dataset_id not in manifests or not match.column_name:
            continue
        key = (dataset_id, match.column_name)
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def _fallback_column_keys(manifests: list[DatasetManifest]) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for manifest in manifests[:4]:
        for column in manifest.columns[:8]:
            keys.append((manifest.dataset_id, column.name))
    return keys


def _limited_sample_rows(
    matches: list[SemanticMatch],
    relevant_keys: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    relevant_by_dataset: dict[str, set[str]] = {}
    for dataset_id, column_name in relevant_keys:
        relevant_by_dataset.setdefault(dataset_id, set()).add(column_name)

    rows: list[dict[str, Any]] = []
    for match in matches:
        if match.kind != "sample_row":
            continue
        payload = match.payload or {}
        row = payload.get("row")
        dataset_id = str(payload.get("dataset_id", ""))
        if not isinstance(row, dict):
            continue
        allowed_columns = relevant_by_dataset.get(dataset_id) or set(list(row.keys())[:4])
        rows.append(
            {
                "dataset_id": dataset_id,
                "filename": payload.get("filename"),
                "row_index": payload.get("row_index"),
                "values": {
                    key: _shorten(value, 160)
                    for key, value in row.items()
                    if key in allowed_columns
                },
            }
        )
        if len(rows) >= 3:
            break
    return rows


def _safe_stats(stats: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "null_count",
        "distinct_count",
        "min_value",
        "max_value",
        "avg_value",
        "stddev_value",
    }
    safe = {key: _shorten(value, 120) for key, value in stats.items() if key in allowed}
    if "top_values" in stats and isinstance(stats["top_values"], list):
        safe["top_values"] = stats["top_values"][:3]
    return safe


def _limited_values(values: list[Any], limit: int) -> list[Any]:
    return [_shorten(value, 120) for value in values[:limit]]


def _shorten(value: Any, max_length: int) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
