from __future__ import annotations

import re
from typing import Any

from backend.models import ColumnProfile, DatasetManifest


class SemanticMetadataGenerator:
    def normalize_column_name(self, name: str) -> str:
        spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
        spaced = re.sub(r"[_\-.]+", " ", spaced)
        spaced = re.sub(r"\s+", " ", spaced)
        return spaced.strip().lower()

    def enrich_columns(self, raw_columns: list[dict[str, Any]]) -> list[ColumnProfile]:
        profiles: list[ColumnProfile] = []
        for column in raw_columns:
            normalized_name = self.normalize_column_name(column["name"])
            semantic_text = self._column_semantic_text(
                name=column["name"],
                normalized_name=normalized_name,
                dtype=column["dtype"],
                sample_values=column.get("sample_values", []),
                stats=column.get("stats", {}),
            )
            profiles.append(
                ColumnProfile(
                    name=column["name"],
                    dtype=column["dtype"],
                    nullable=column.get("nullable", True),
                    normalized_name=normalized_name,
                    sample_values=column.get("sample_values", []),
                    stats=column.get("stats", {}),
                    semantic_text=semantic_text,
                )
            )
        return profiles

    def build_documents(self, manifest: DatasetManifest) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []

        # ── 1. Dataset-level summary ──────────────────────────────────
        schema_summary = ", ".join(
            f"{column.name} ({column.normalized_name}, {column.dtype})" for column in manifest.columns
        )
        documents.append(
            {
                "document_id": f"{manifest.dataset_id}:dataset",
                "kind": "dataset",
                "text": (
                    f"Parquet file {manifest.filename}. Dataset schema with {manifest.row_count} rows. "
                    f"Columns: {schema_summary}."
                ),
                "payload": {
                    "dataset_id": manifest.dataset_id,
                    "filename": manifest.filename,
                    "kind": "dataset",
                    "columns": [column.name for column in manifest.columns],
                    "row_count": manifest.row_count,
                },
            }
        )

        # ── 2. Rich column-level chunks ───────────────────────────────
        for column in manifest.columns:
            rich_text = self._rich_column_chunk(column, manifest.filename)
            documents.append(
                {
                    "document_id": f"{manifest.dataset_id}:column:{column.name}",
                    "kind": "column",
                    "text": rich_text,
                    "payload": {
                        "dataset_id": manifest.dataset_id,
                        "filename": manifest.filename,
                        "kind": "column",
                        "column_name": column.name,
                        "normalized_name": column.normalized_name,
                        "dtype": column.dtype,
                        "datatype": self._broad_type(column.dtype),
                        "stats": column.stats,
                        "sample_values": column.sample_values[:5],
                        "semantic_chunk": rich_text,
                    },
                }
            )

        # ── 3. High-cardinality value chunks ──────────────────────────
        for column in manifest.columns:
            distinct = column.stats.get("distinct_count")
            if distinct and distinct > 50 and not self._is_numeric_type(column.dtype):
                top_values = column.stats.get("top_values", [])
                if top_values:
                    vals = [str(v.get("value", v)) if isinstance(v, dict) else str(v)
                            for v in top_values[:20]]
                    value_text = (
                        f"{column.name} | high-cardinality column in {manifest.filename} "
                        f"| {distinct} unique values | top values: {', '.join(vals)}"
                    )
                    documents.append(
                        {
                            "document_id": f"{manifest.dataset_id}:values:{column.name}",
                            "kind": "value_list",
                            "text": value_text[:1024],  # max 256 tokens ≈ ~1024 chars
                            "payload": {
                                "dataset_id": manifest.dataset_id,
                                "filename": manifest.filename,
                                "kind": "value_list",
                                "column_name": column.name,
                                "dtype": column.dtype,
                                "datatype": self._broad_type(column.dtype),
                                "distinct_count": distinct,
                            },
                        }
                    )

        # ── 4. Sample row chunks ──────────────────────────────────────
        for index, row in enumerate(manifest.sample_rows[:5]):
            values = "; ".join(f"{key}: {value}" for key, value in row.items())
            documents.append(
                {
                    "document_id": f"{manifest.dataset_id}:sample:{index}",
                    "kind": "sample_row",
                    "text": f"Sample row from {manifest.filename}. {values}",
                    "payload": {
                        "dataset_id": manifest.dataset_id,
                        "filename": manifest.filename,
                        "kind": "sample_row",
                        "row_index": index,
                        "row": row,
                    },
                }
            )

        return documents

    # ── rich column chunk (replaces old semantic_text for embedding) ──

    def _rich_column_chunk(self, column: ColumnProfile, filename: str) -> str:
        """Build a rich semantic chunk per the spec:
        {column_name} | type: {dtype} | sample values: {top_5} |
        stats: min={min}, max={max}, nulls={null_pct}% | file: {filename}
        """
        samples = ", ".join(str(v) for v in column.sample_values[:5])
        parts = [
            f"{column.name}",
            f"type: {column.dtype}",
            f"sample values: {samples or 'none'}",
        ]

        # stats
        stats = column.stats
        stat_items: list[str] = []
        if stats.get("min_value") is not None:
            stat_items.append(f"min={stats['min_value']}")
        if stats.get("max_value") is not None:
            stat_items.append(f"max={stats['max_value']}")
        if stats.get("avg_value") is not None:
            stat_items.append(f"avg={stats['avg_value']}")
        if stats.get("null_count") is not None and stats.get("distinct_count") is not None:
            total = stats.get("null_count", 0) + stats.get("distinct_count", 0)
            null_pct = round(stats["null_count"] / max(total, 1) * 100, 1)
            stat_items.append(f"nulls={null_pct}%")
        if stats.get("distinct_count") is not None:
            stat_items.append(f"distinct={stats['distinct_count']}")

        if stat_items:
            parts.append(f"stats: {', '.join(stat_items)}")

        parts.append(f"file: {filename}")

        return " | ".join(parts)

    def _column_semantic_text(
        self,
        name: str,
        normalized_name: str,
        dtype: str,
        sample_values: list[Any],
        stats: dict[str, Any],
    ) -> str:
        examples = ", ".join(str(value) for value in sample_values[:6])
        stats_text = ", ".join(f"{key}: {value}" for key, value in stats.items() if value not in (None, [], {}))
        return (
            f"Column {name}. Normalized label: {normalized_name}. "
            f"Data type: {dtype}. Example values: {examples or 'no non-null examples available'}. "
            f"Profile statistics: {stats_text or 'not available'}."
        )

    @staticmethod
    def _broad_type(dtype: str) -> str:
        """Map detailed DuckDB type to a broad category for payload indexing."""
        upper = dtype.upper()
        if any(m in upper for m in ("INT", "BIGINT", "SMALLINT", "TINYINT", "HUGEINT")):
            return "integer"
        if any(m in upper for m in ("FLOAT", "DOUBLE", "DECIMAL", "REAL")):
            return "float"
        if any(m in upper for m in ("DATE", "TIME", "TIMESTAMP")):
            return "datetime"
        if any(m in upper for m in ("BOOL",)):
            return "boolean"
        return "string"

    @staticmethod
    def _is_numeric_type(dtype: str) -> bool:
        upper = dtype.upper()
        return any(m in upper for m in (
            "INT", "BIGINT", "SMALLINT", "TINYINT", "FLOAT", "DOUBLE", "DECIMAL", "REAL",
        ))
