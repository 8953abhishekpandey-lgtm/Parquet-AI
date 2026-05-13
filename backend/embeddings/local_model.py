from __future__ import annotations

from threading import Lock

from backend.core.config import get_settings


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

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self.model.encode(
            texts,
            batch_size=self.settings.embedding_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()
