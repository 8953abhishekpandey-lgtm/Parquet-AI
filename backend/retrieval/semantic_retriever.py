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
        vector = self.embeddings.encode([question])[0]
        return self.vector_store.search(dataset_id, vector, self.settings.semantic_top_k)

    def search_all(self, question: str, dataset_ids: list[str] | None = None) -> list[SemanticMatch]:
        vector = self.embeddings.encode([question])[0]
        return self.vector_store.search_many(
            query_vector=vector,
            limit=self.settings.semantic_top_k * 3,
            dataset_ids=dataset_ids,
        )
