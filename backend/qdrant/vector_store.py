from __future__ import annotations

import atexit
import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from backend.core.config import get_settings
from backend.models import SemanticMatch

logger = logging.getLogger(__name__)


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
                    "or start server mode with: docker compose up -d qdrant"
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

        # Create collection with HNSW tuning and cosine distance
        self.client.create_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(
                size=vector_size,
                distance=qmodels.Distance.COSINE,
            ),
            hnsw_config=qmodels.HnswConfigDiff(
                m=16,
                ef_construct=200,
            ),
        )

        # Create payload indexes for filtered retrieval
        for field_name, field_type in [
            ("filename", qmodels.PayloadSchemaType.KEYWORD),
            ("column_name", qmodels.PayloadSchemaType.KEYWORD),
            ("datatype", qmodels.PayloadSchemaType.KEYWORD),
            ("dataset_id", qmodels.PayloadSchemaType.KEYWORD),
            ("kind", qmodels.PayloadSchemaType.KEYWORD),
        ]:
            try:
                self.client.create_payload_index(
                    collection_name=collection,
                    field_name=field_name,
                    field_schema=field_type,
                )
            except Exception:
                pass  # index may already exist

        logger.info(
            "Created Qdrant collection '%s' with HNSW(m=16, ef_construct=200) and payload indexes",
            collection,
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

    def search(
        self,
        dataset_id: str,
        query_vector: list[float],
        limit: int,
        score_threshold: float | None = None,
    ) -> list[SemanticMatch]:
        query_filter = self._dataset_filter(dataset_id)
        return self._search_with_filter(query_vector, limit, query_filter, score_threshold)

    def search_many(
        self,
        query_vector: list[float],
        limit: int,
        dataset_ids: list[str] | None = None,
        score_threshold: float | None = None,
    ) -> list[SemanticMatch]:
        query_filter = self._dataset_filter_many(dataset_ids) if dataset_ids else None
        return self._search_with_filter(query_vector, limit, query_filter, score_threshold)

    def _search_with_filter(
        self,
        query_vector: list[float],
        limit: int,
        query_filter: qmodels.Filter | None,
        score_threshold: float | None = None,
    ) -> list[SemanticMatch]:
        collection = self.settings.qdrant_collection

        search_kwargs: dict[str, Any] = {
            "collection_name": collection,
            "query_vector": query_vector,
            "query_filter": query_filter,
            "limit": limit,
            "with_payload": True,
        }
        if score_threshold is not None:
            search_kwargs["score_threshold"] = score_threshold

        if hasattr(self.client, "search"):
            hits = self.client.search(**search_kwargs)
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

    def is_connected(self) -> bool:
        """Check if Qdrant is reachable (used by health endpoint)."""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False
