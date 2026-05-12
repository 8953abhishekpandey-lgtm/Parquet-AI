from pathlib import Path

from fastapi import UploadFile

from backend.core.config import get_settings
from backend.duckdb.client import DuckDBAnalytics
from backend.embeddings.local_model import LocalEmbeddingModel
from backend.metadata.generator import SemanticMetadataGenerator
from backend.models import DatasetManifest, QueryAllRequest, QueryRequest, QueryResponse
from backend.qdrant.vector_store import QdrantVectorStore
from backend.retrieval.semantic_retriever import SemanticRetriever
from backend.services.file_service import FileStorageService
from backend.services.response_builder import TemplateResponseBuilder
from backend.spark.session import SparkSchemaReader
from backend.sql_generation.multi_table_rules import MultiTableSQLGenerator
from backend.sql_generation.rules import RuleBasedSQLGenerator


class AnalyticsPipeline:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.files = FileStorageService()
        self.duckdb = DuckDBAnalytics()
        self.spark = SparkSchemaReader()
        self.metadata = SemanticMetadataGenerator()
        self.embeddings = LocalEmbeddingModel()
        self.vector_store = QdrantVectorStore()
        self.retriever = SemanticRetriever()
        self.sql_generator = RuleBasedSQLGenerator()
        self.multi_sql_generator = MultiTableSQLGenerator()
        self.response_builder = TemplateResponseBuilder()

    async def ingest_upload(self, upload: UploadFile) -> DatasetManifest:
        dataset_id, filename, stored_path = await self.files.save_upload(upload)

        duckdb_profile = self.duckdb.inspect_parquet(stored_path)
        spark_schema = self.spark.inspect(stored_path)
        columns = self.metadata.enrich_columns(duckdb_profile["columns"])

        manifest = DatasetManifest(
            dataset_id=dataset_id,
            filename=filename,
            stored_path=str(stored_path),
            uploaded_at=self.files.utc_now(),
            row_count=duckdb_profile["row_count"],
            columns=columns,
            sample_rows=duckdb_profile["sample_rows"],
            spark_schema=spark_schema,
            metadata_count=0,
        )

        documents = self.metadata.build_documents(manifest)
        vectors = self.embeddings.encode([document["text"] for document in documents])
        self.vector_store.ensure_collection(self.embeddings.dimension)
        self.vector_store.replace_dataset_documents(dataset_id, documents, vectors)

        manifest.metadata_count = len(documents)
        self.files.save_manifest(manifest)
        return manifest

    def list_datasets(self) -> list[DatasetManifest]:
        return self.files.list_manifests()

    def get_dataset(self, dataset_id: str) -> DatasetManifest:
        return self.files.load_manifest(dataset_id)

    def answer_question(self, request: QueryRequest) -> QueryResponse:
        question = request.question.strip()
        if not question:
            raise ValueError("Question cannot be empty.")

        manifest = self.files.load_manifest(request.dataset_id)
        parquet_path = Path(manifest.stored_path)
        if not parquet_path.exists():
            raise FileNotFoundError(f"Stored parquet file not found for dataset {request.dataset_id}.")

        matches = self.retriever.search(manifest.dataset_id, question)
        plan = self.sql_generator.generate(
            question=question,
            manifest=manifest,
            matches=matches,
            limit=min(request.limit, self.settings.query_row_limit),
            exact=getattr(request, "exact", False),
        )
        columns, rows = self.duckdb.execute_sql(parquet_path, plan.sql, plan.limit)
        answer = self.response_builder.build(plan, rows)

        return QueryResponse(
            dataset_id=manifest.dataset_id,
            question=question,
            answer=answer,
            semantic_matches=matches,
            generated_sql=plan,
            columns=columns,
            rows=rows,
            row_count=len(rows),
        )

    def answer_question_all(self, request: QueryAllRequest) -> QueryResponse:
        question = request.question.strip()
        if not question:
            raise ValueError("Question cannot be empty.")

        if request.dataset_ids:
            manifests = [self.files.load_manifest(dataset_id) for dataset_id in request.dataset_ids]
        else:
            manifests = self.files.list_manifests()

        if not manifests:
            raise ValueError("Upload at least one parquet file before querying all datasets.")

        for manifest in manifests:
            parquet_path = Path(manifest.stored_path)
            if not parquet_path.exists():
                raise FileNotFoundError(f"Stored parquet file not found for dataset {manifest.dataset_id}.")

        dataset_ids = [manifest.dataset_id for manifest in manifests]
        matches = self.retriever.search_all(question, dataset_ids)
        relation_map = self.duckdb.create_relation_map(manifests)
        plan = self.multi_sql_generator.generate(
            question=question,
            manifests=manifests,
            matches=matches,
            relation_map=relation_map,
            limit=min(request.limit, self.settings.query_row_limit),
            exact=getattr(request, "exact", False),
        )
        relation_paths = {
            relation_map[manifest.dataset_id]: manifest.stored_path
            for manifest in manifests
        }
        columns, rows = self.duckdb.execute_sql_many(relation_paths, plan.sql, plan.limit)
        answer = self.response_builder.build(plan, rows)

        return QueryResponse(
            dataset_id="all",
            question=question,
            answer=answer,
            semantic_matches=matches,
            generated_sql=plan,
            columns=columns,
            rows=rows,
            row_count=len(rows),
        )

    def delete_dataset(self, dataset_id: str) -> None:
        try:
            # remove vectors first (best-effort)
            try:
                self.vector_store.delete_dataset(dataset_id)
            except Exception:
                pass

            # remove stored file and manifest
            self.files.delete_dataset(dataset_id)
        except FileNotFoundError:
            raise
