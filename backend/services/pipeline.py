from pathlib import Path
from typing import Any

from fastapi import UploadFile

from backend.anthropic.client import AnthropicRAGClient
from backend.anthropic.context import build_minimal_rag_context, build_result_context
from backend.core.config import get_settings
from backend.duckdb.client import DuckDBAnalytics
from backend.embeddings.local_model import LocalEmbeddingModel
from backend.metadata.generator import SemanticMetadataGenerator
from backend.models import DatasetManifest, GeneratedSQL, QueryAllRequest, QueryRequest, QueryResponse
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
        self.anthropic = AnthropicRAGClient()

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
        fallback_plan = self.sql_generator.generate(
            question=question,
            manifest=manifest,
            matches=matches,
            limit=min(request.limit, self.settings.query_row_limit),
            exact=getattr(request, "exact", False),
        )
        rag_context = build_minimal_rag_context(
            question=question,
            manifests=[manifest],
            matches=matches,
            limit=min(request.limit, self.settings.query_row_limit),
            candidate_plan=fallback_plan,
        )
        plan, sql_usage, fallback_reason = self._generate_single_plan(
            question=question,
            parquet_path=parquet_path,
            rag_context=rag_context,
            fallback_plan=fallback_plan,
        )
        columns, rows = self.duckdb.execute_sql(parquet_path, plan.sql, plan.limit)
        answer, answer_usage, result_context = self._build_final_answer(question, plan, columns, rows)

        return QueryResponse(
            dataset_id=manifest.dataset_id,
            question=question,
            answer=answer,
            semantic_matches=matches,
            generated_sql=plan,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            rag_context=self._response_context(rag_context, result_context),
            llm_usage=self._llm_usage(sql_usage, answer_usage, fallback_reason),
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
        fallback_plan = self.multi_sql_generator.generate(
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
        rag_context = build_minimal_rag_context(
            question=question,
            manifests=manifests,
            matches=matches,
            limit=min(request.limit, self.settings.query_row_limit),
            relation_map=relation_map,
            candidate_plan=fallback_plan,
        )
        plan, sql_usage, fallback_reason = self._generate_multi_plan(
            question=question,
            relation_paths=relation_paths,
            rag_context=rag_context,
            fallback_plan=fallback_plan,
        )
        columns, rows = self.duckdb.execute_sql_many(relation_paths, plan.sql, plan.limit)
        answer, answer_usage, result_context = self._build_final_answer(question, plan, columns, rows)

        return QueryResponse(
            dataset_id="all",
            question=question,
            answer=answer,
            semantic_matches=matches,
            generated_sql=plan,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            rag_context=self._response_context(rag_context, result_context),
            llm_usage=self._llm_usage(sql_usage, answer_usage, fallback_reason),
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

    def _generate_single_plan(
        self,
        *,
        question: str,
        parquet_path: Path,
        rag_context: dict[str, Any],
        fallback_plan: GeneratedSQL,
    ) -> tuple[GeneratedSQL, dict[str, Any], str | None]:
        if self.anthropic.available:
            previous_sql: str | None = None
            previous_error: str | None = None
            usage: dict[str, Any] = {}
            for attempt in range(self.settings.sql_retry_attempts + 1):
                candidate: GeneratedSQL | None = None
                try:
                    candidate, call_usage = self.anthropic.generate_sql(
                        question=question,
                        rag_context=rag_context,
                        previous_sql=previous_sql,
                        previous_error=previous_error,
                        attempt=attempt,
                    )
                    usage[f"attempt_{attempt + 1}"] = call_usage
                    candidate.sql = self.duckdb.validate_sql(parquet_path, candidate.sql)
                    candidate.validated = True
                    candidate.retry_count = attempt
                    return candidate, usage, None
                except Exception as exc:
                    previous_sql = candidate.sql if candidate else previous_sql
                    previous_error = str(exc)
            fallback_reason = f"Claude SQL generation failed validation; used local fallback. Last error: {previous_error}"
            fallback_plan = self._validate_fallback_single(parquet_path, fallback_plan)
            return fallback_plan, usage, fallback_reason

        fallback_plan = self._validate_fallback_single(parquet_path, fallback_plan)
        return fallback_plan, {}, "ANTHROPIC_API_KEY is not configured; used local SQL fallback."

    def _generate_multi_plan(
        self,
        *,
        question: str,
        relation_paths: dict[str, str | Path],
        rag_context: dict[str, Any],
        fallback_plan: GeneratedSQL,
    ) -> tuple[GeneratedSQL, dict[str, Any], str | None]:
        if self.anthropic.available:
            previous_sql: str | None = None
            previous_error: str | None = None
            usage: dict[str, Any] = {}
            for attempt in range(self.settings.sql_retry_attempts + 1):
                candidate: GeneratedSQL | None = None
                try:
                    candidate, call_usage = self.anthropic.generate_sql(
                        question=question,
                        rag_context=rag_context,
                        previous_sql=previous_sql,
                        previous_error=previous_error,
                        attempt=attempt,
                    )
                    usage[f"attempt_{attempt + 1}"] = call_usage
                    candidate.sql = self.duckdb.validate_sql_many(relation_paths, candidate.sql)
                    candidate.validated = True
                    candidate.retry_count = attempt
                    return candidate, usage, None
                except Exception as exc:
                    previous_sql = candidate.sql if candidate else previous_sql
                    previous_error = str(exc)
            fallback_reason = f"Claude SQL generation failed validation; used local fallback. Last error: {previous_error}"
            fallback_plan = self._validate_fallback_many(relation_paths, fallback_plan)
            return fallback_plan, usage, fallback_reason

        fallback_plan = self._validate_fallback_many(relation_paths, fallback_plan)
        return fallback_plan, {}, "ANTHROPIC_API_KEY is not configured; used local SQL fallback."

    def _validate_fallback_single(self, parquet_path: Path, fallback_plan: GeneratedSQL) -> GeneratedSQL:
        fallback_plan.sql = self.duckdb.validate_sql(parquet_path, fallback_plan.sql)
        fallback_plan.validated = True
        fallback_plan.source = "local_rules"
        return fallback_plan

    def _validate_fallback_many(
        self,
        relation_paths: dict[str, str | Path],
        fallback_plan: GeneratedSQL,
    ) -> GeneratedSQL:
        fallback_plan.sql = self.duckdb.validate_sql_many(relation_paths, fallback_plan.sql)
        fallback_plan.validated = True
        fallback_plan.source = "local_rules"
        return fallback_plan

    def _build_final_answer(
        self,
        question: str,
        plan: GeneratedSQL,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        result_context = build_result_context(
            question=question,
            plan=plan,
            columns=columns,
            rows=rows,
        )
        if self.anthropic.available:
            try:
                answer, usage = self.anthropic.summarize_answer(
                    question=question,
                    result_context=result_context,
                )
                return answer, usage, result_context
            except Exception as exc:
                return self.response_builder.build(plan, rows), {"error": str(exc)}, result_context
        return self.response_builder.build(plan, rows), {}, result_context

    def _response_context(
        self,
        sql_context: dict[str, Any],
        result_context: dict[str, Any],
    ) -> dict[str, Any]:
        result_policy = dict(result_context.get("security_policy", {}))
        if not self.anthropic.available:
            result_policy["result_rows_sent_to_llm"] = 0
            result_policy["reason"] = "Anthropic is not configured or disabled."
        return {
            "sql_generation_context_sent_to_llm": sql_context if self.anthropic.available else None,
            "answer_context_sent_to_llm": result_context if self.anthropic.available else None,
            "local_retrieval_context": sql_context,
            "result_preview_policy": result_policy,
        }

    def _llm_usage(
        self,
        sql_usage: dict[str, Any],
        answer_usage: dict[str, Any],
        fallback_reason: str | None,
    ) -> dict[str, Any]:
        usage = self.anthropic.base_usage()
        usage.update(
            {
                "sql_generation": sql_usage,
                "answer_generation": answer_usage,
                "fallback_reason": fallback_reason,
            }
        )
        return usage
