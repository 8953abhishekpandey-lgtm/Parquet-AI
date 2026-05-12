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

        for column in manifest.columns:
            documents.append(
                {
                    "document_id": f"{manifest.dataset_id}:column:{column.name}",
                    "kind": "column",
                    "text": column.semantic_text,
                    "payload": {
                        "dataset_id": manifest.dataset_id,
                        "filename": manifest.filename,
                        "kind": "column",
                        "column_name": column.name,
                        "normalized_name": column.normalized_name,
                        "dtype": column.dtype,
                        "stats": column.stats,
                        "sample_values": column.sample_values,
                    },
                }
            )

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

