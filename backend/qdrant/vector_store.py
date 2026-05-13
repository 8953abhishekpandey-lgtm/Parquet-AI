from __future__ import annotations

import atexit
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from backend.core.config import get_settings
from backend.models import SemanticMatch


class QdrantVectorStore:
    _shared_client: QdrantClient | None = None
    _atexit_registered = False

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def client(self) -> QdrantClient:
        if QdrantVectorStore._shared_client is None:
            try:
                if self.settings.qdrant_mode.lower() == "embedded":
                    QdrantVectorStore._shared_client = QdrantClient(path=str(self.settings.qdrant_local_path))
                else:
                    kwargs: dict[str, Any] = {"url": self.settings.qdrant_url}
                    if self.settings.qdrant_api_key:
                        kwargs["api_key"] = self.settings.qdrant_api_key
                    QdrantVectorStore._shared_client = QdrantClient(**kwargs)
                QdrantVectorStore._shared_client.get_collections()
                if not QdrantVectorStore._atexit_registered:
                    atexit.register(QdrantVectorStore.close_shared_client)
                    QdrantVectorStore._atexit_registered = True
            except Exception as exc:
                raise ConnectionError(
                    "Qdrant is not reachable. Use embedded mode with QDRANT_MODE=embedded "
                    "or start server mode with: docker compose up -d qdrant. "
                    f"Underlying error: {exc}"
                ) from exc
        return QdrantVectorStore._shared_client

    @classmethod
    def close_shared_client(cls) -> None:
        if cls._shared_client is not None:
            cls._shared_client.close()
            cls._shared_client = None

    def ensure_collection(self, vector_size: int) -> None:
        collection = self.settings.qdrant_collection
        collections = self.client.get_collections().collections
        exists = any(item.name == collection for item in collections)
        if exists:
            info = self.client.get_collection(collection)
            configured_size = info.config.params.vectors.size
            if configured_size != vector_size:
                raise ValueError(
                    f"Qdrant collection {collection} uses vector size {configured_size}, "
                    f"but the embedding model produced {vector_size}."
                )
            return

        self.client.create_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
        )

    def replace_dataset_documents(self, dataset_id: str, documents: list[dict[str, Any]], vectors: list[list[float]]) -> None:
        self.delete_dataset(dataset_id)
        points = []
        for document, vector in zip(documents, vectors, strict=True):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, document["document_id"]))
            payload = document["payload"] | {
                "document_id": document["document_id"],
                "text": document["text"],
            }
            points.append(qmodels.PointStruct(id=point_id, vector=vector, payload=payload))

        if points:
            self.client.upsert(collection_name=self.settings.qdrant_collection, points=points)

    def delete_dataset(self, dataset_id: str) -> None:
        self.client.delete(
            collection_name=self.settings.qdrant_collection,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="dataset_id",
                            match=qmodels.MatchValue(value=dataset_id),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def search(self, dataset_id: str, query_vector: list[float], limit: int) -> list[SemanticMatch]:
        query_filter = self._dataset_filter(dataset_id)
        return self._search_with_filter(query_vector, limit, query_filter)

    def search_many(
        self,
        query_vector: list[float],
        limit: int,
        dataset_ids: list[str] | None = None,
    ) -> list[SemanticMatch]:
        query_filter = self._dataset_filter_many(dataset_ids) if dataset_ids else None
        return self._search_with_filter(query_vector, limit, query_filter)

    def _search_with_filter(
        self,
        query_vector: list[float],
        limit: int,
        query_filter: qmodels.Filter | None,
    ) -> list[SemanticMatch]:
        collection = self.settings.qdrant_collection

        if hasattr(self.client, "search"):
            hits = self.client.search(
                collection_name=collection,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        else:
            result = self.client.query_points(
                collection_name=collection,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            hits = result.points

        matches: list[SemanticMatch] = []
        for hit in hits:
            payload = dict(hit.payload or {})
            matches.append(
                SemanticMatch(
                    score=float(hit.score),
                    kind=str(payload.get("kind", "metadata")),
                    column_name=payload.get("column_name"),
                    text=str(payload.get("text", "")),
                    payload=payload,
                )
            )
        return matches

    def _dataset_filter(self, dataset_id: str) -> qmodels.Filter:
        return qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="dataset_id",
                    match=qmodels.MatchValue(value=dataset_id),
                )
            ]
        )

    def _dataset_filter_many(self, dataset_ids: list[str] | None) -> qmodels.Filter | None:
        if not dataset_ids:
            return None
        return qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="dataset_id",
                    match=qmodels.MatchAny(any=dataset_ids),
                )
            ]
        )
