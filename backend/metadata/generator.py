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
            profiles.append(
                ColumnProfile(
                    name=column["name"],
                    dtype=column["dtype"],
                    nullable=column.get("nullable", True),
                    normalized_name=normalized_name,
                    sample_values=column.get("sample_values", []),
                    stats=column.get("stats", {}),
                    semantic_text="",
                )
            )
        return profiles

    def build_documents(self, manifest: DatasetManifest, join_map: dict[str, list[str]] = None) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        if join_map is None:
            join_map = {}

        file_path = manifest.stored_path

        # ── CHUNK TYPE 3: File-Level Summary Chunk ──────────────────────────────────
        schema_summary = ", ".join(
            f"{column.name} ({column.dtype})" for column in manifest.columns
        )
        key_columns = [c.name for c in manifest.columns if c.stats.get("distinct_count", 0) > 0][:5]
        
        file_text = (
            f"File '{manifest.filename}' contains {manifest.row_count} rows and {len(manifest.columns)} columns: "
            f"{schema_summary}. "
            f"Key columns: {', '.join(key_columns) if key_columns else 'none'}."
        )
        
        documents.append(
            {
                "document_id": f"{manifest.dataset_id}:file_summary",
                "kind": "file_summary",
                "text": file_text,
                "payload": {
                    "dataset_id": manifest.dataset_id,
                    "filename": manifest.filename,
                    "chunk_type": "file_summary",
                    "semantic_chunk_text": file_text,
                    "file_path": file_path,
                },
            }
        )

        # ── CHUNK TYPE 1: Column Semantic Chunk ───────────────────────────────
        for column in manifest.columns:
            samples = ", ".join(str(v) for v in column.sample_values[:5])
            
            stats = column.stats
            min_val = stats.get("min_value")
            max_val = stats.get("max_value")
            
            total = stats.get("null_count", 0) + stats.get("distinct_count", 0)
            null_pct = round(stats["null_count"] / max(total, 1) * 100, 1) if "null_count" in stats else 0
            
            col_text = (
                f"Column '{column.name}' in file '{manifest.filename}' stores {column.dtype} data. "
                f"Sample values: {samples if samples else 'none'}. "
                f"Stats: min={min_val}, max={max_val}, null_rate={null_pct}%. "
                f"Semantic meaning: {column.normalized_name} data."
            )
            
            documents.append(
                {
                    "document_id": f"{manifest.dataset_id}:column:{column.name}",
                    "kind": "column",
                    "text": col_text,
                    "payload": {
                        "dataset_id": manifest.dataset_id,
                        "filename": manifest.filename,
                        "column_name": column.name,
                        "datatype": self._broad_type(column.dtype),
                        "chunk_type": "column",
                        "semantic_chunk_text": col_text,
                        "sample_values": [str(v) for v in column.sample_values[:5]],
                        "stats": stats,
                        "min_val": min_val,
                        "max_val": max_val,
                        "null_pct": null_pct,
                        "file_path": file_path,
                    },
                }
            )

        # ── CHUNK TYPE 2: Row Group Chunk (for categorical columns) ──────────────────────────
        for column in manifest.columns:
            distinct = column.stats.get("distinct_count")
            if distinct and distinct <= 50 and not self._is_numeric_type(column.dtype):
                top_values = column.stats.get("top_values", [])
                if top_values:
                    vals = [str(v.get("value", v)) if isinstance(v, dict) else str(v)
                            for v in top_values[:20]]
                    cat_text = (
                        f"In file '{manifest.filename}', column '{column.name}' contains categories: "
                        f"{', '.join(vals)}"
                    )
                    documents.append(
                        {
                            "document_id": f"{manifest.dataset_id}:categories:{column.name}",
                            "kind": "row_group",
                            "text": cat_text,
                            "payload": {
                                "dataset_id": manifest.dataset_id,
                                "filename": manifest.filename,
                                "column_name": column.name,
                                "datatype": self._broad_type(column.dtype),
                                "chunk_type": "row_group",
                                "semantic_chunk_text": cat_text,
                                "file_path": file_path,
                            },
                        }
                    )

        # ── CHUNK TYPE 4: Relationship Chunk (for joinable columns) ───────────────────────────────
        for column in manifest.columns:
            other_files = [f for f in join_map.get(column.name, []) if f != manifest.filename]
            if other_files:
                rel_text = (
                    f"Column '{column.name}' in '{manifest.filename}' appears to be a join key. "
                    f"Matching columns found in: {', '.join(other_files)}"
                )
                documents.append(
                    {
                        "document_id": f"{manifest.dataset_id}:relationship:{column.name}",
                        "kind": "relationship",
                        "text": rel_text,
                        "payload": {
                            "dataset_id": manifest.dataset_id,
                            "filename": manifest.filename,
                            "column_name": column.name,
                            "chunk_type": "relationship",
                            "semantic_chunk_text": rel_text,
                            "file_path": file_path,
                        },
                    }
                )

        return documents

    @staticmethod
    def _broad_type(dtype: str) -> str:
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
