from __future__ import annotations

from backend.core.config import get_settings
from backend.embeddings.local_model import LocalEmbeddingModel
from backend.models import SemanticMatch
from backend.qdrant.vector_store import QdrantVectorStore


class SemanticRetriever:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.embeddings = LocalEmbeddingModel()
        self.vector_store = QdrantVectorStore()

    def search(self, dataset_id: str, question: str) -> list[SemanticMatch]:
        # Use encode_queries for BGE prefix support
        vector = self.embeddings.encode_queries([question])[0]
        matches = self.vector_store.search(
            dataset_id,
            vector,
            self.settings.semantic_top_k,
            score_threshold=self.settings.score_threshold,
        )
        return self._deduplicate_and_group(matches)

    def search_all(self, question: str, dataset_ids: list[str] | None = None) -> list[SemanticMatch]:
        # Use encode_queries for BGE prefix support
        vector = self.embeddings.encode_queries([question])[0]
        matches = self.vector_store.search_many(
            query_vector=vector,
            limit=self.settings.semantic_top_k * 3,
            dataset_ids=dataset_ids,
            score_threshold=self.settings.score_threshold,
        )
        return self._deduplicate_and_group(matches)

    @staticmethod
    def _deduplicate_and_group(matches: list[SemanticMatch]) -> list[SemanticMatch]:
        """Deduplicate by column_name (keep highest score) and group by filename."""
        seen_columns: dict[str, SemanticMatch] = {}
        non_column_matches: list[SemanticMatch] = []

        for match in matches:
            if match.column_name:
                key = f"{match.payload.get('filename', '')}::{match.column_name}"
                if key not in seen_columns or match.score > seen_columns[key].score:
                    seen_columns[key] = match
            else:
                non_column_matches.append(match)

        # Combine and sort: column matches first (grouped by file), then others
        deduped = list(seen_columns.values())
        # Group by filename, then by score within each group
        deduped.sort(key=lambda m: (m.payload.get("filename", ""), -m.score))
        non_column_matches.sort(key=lambda m: -m.score)

        return deduped + non_column_matches
