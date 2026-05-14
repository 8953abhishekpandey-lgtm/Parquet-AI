from __future__ import annotations

from threading import Lock

from backend.core.config import get_settings

# BGE models require a query prefix for retrieval tasks
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
_BGE_MODEL_MARKERS = ("bge-",)


class LocalEmbeddingModel:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._model = None
        self._lock = Lock()

    @property
    def model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    # load model from settings; use a higher-quality default if available
                    self._model = SentenceTransformer(self.settings.embedding_model)
        return self._model

    @property
    def dimension(self) -> int:
        if hasattr(self.model, "get_embedding_dimension"):
            return int(self.model.get_embedding_dimension())
        return int(self.model.get_sentence_embedding_dimension())

    @property
    def _is_bge(self) -> bool:
        model_name = self.settings.embedding_model.lower()
        return any(marker in model_name for marker in _BGE_MODEL_MARKERS)

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode document texts (no prefix)."""
        if not texts:
            return []
        vectors = self.model.encode(
            texts,
            batch_size=self.settings.embedding_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def encode_queries(self, queries: list[str]) -> list[list[float]]:
        """Encode query texts — adds BGE query prefix when using a BGE model."""
        if not queries:
            return []
        if self._is_bge:
            queries = [f"{_BGE_QUERY_PREFIX}{q}" for q in queries]
        vectors = self.model.encode(
            queries,
            batch_size=self.settings.embedding_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()
