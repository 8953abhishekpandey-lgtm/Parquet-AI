import time
from pathlib import Path
import logging

from fastapi import UploadFile

from backend.core.config import get_settings
from backend.anthropic.claude_client import ClaudeReasoningEngine
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

logger = logging.getLogger(__name__)


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
        self.claude = ClaudeReasoningEngine()

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

        t_start = time.perf_counter()

        manifest = self.files.load_manifest(request.dataset_id)
        parquet_path = Path(manifest.stored_path)
        if not parquet_path.exists():
            raise FileNotFoundError(f"Stored parquet file not found for dataset {request.dataset_id}.")

        # Step 1: LOCAL semantic retrieval from Qdrant
        matches = self.retriever.search(manifest.dataset_id, question)

        # Step 2: Try Claude for SQL generation, fallback to rule-based
        security_audit = {}
        ai_reasoning = ""

        if self.claude.available and not getattr(request, "exact", False):
            try:
                plan, security_audit = self.claude.generate_sql(
                    question=question,
                    manifest=manifest,
                    matches=matches,
                    limit=min(request.limit, self.settings.query_row_limit),
                )
                logger.info("Claude SQL generated: %s", plan.sql[:100])
            except Exception as exc:
                logger.warning("Claude SQL generation failed, falling back to rule-based: %s", exc)
                plan = self.sql_generator.generate(
                    question=question,
                    manifest=manifest,
                    matches=matches,
                    limit=min(request.limit, self.settings.query_row_limit),
                    exact=getattr(request, "exact", False),
                )
        else:
            plan = self.sql_generator.generate(
                question=question,
                manifest=manifest,
                matches=matches,
                limit=min(request.limit, self.settings.query_row_limit),
                exact=getattr(request, "exact", False),
            )

        # Step 3: LOCAL DuckDB SQL execution — NEVER leaves the system
        try:
            columns, rows = self.duckdb.execute_sql(parquet_path, plan.sql, plan.limit)
        except Exception as sql_exc:
            logger.warning("SQL execution failed (%s), attempting Claude fix", sql_exc)
            # Retry: send error back to Claude for a one-shot fix
            if self.claude.available:
                try:
                    fixed_plan = self.claude.fix_sql_error(
                        original_sql=plan.sql,
                        error_message=str(sql_exc),
                        limit=plan.limit,
                    )
                    columns, rows = self.duckdb.execute_sql(parquet_path, fixed_plan.sql, fixed_plan.limit)
                    plan = fixed_plan
                    logger.info("Claude SQL fix succeeded: %s", plan.sql[:100])
                except Exception as fix_exc:
                    logger.warning("Claude SQL fix also failed (%s), falling back to rule-based", fix_exc)
                    plan = self.sql_generator.generate(
                        question=question,
                        manifest=manifest,
                        matches=matches,
                        limit=min(request.limit, self.settings.query_row_limit),
                        exact=getattr(request, "exact", False),
                    )
                    columns, rows = self.duckdb.execute_sql(parquet_path, plan.sql, plan.limit)
            else:
                # No Claude — fall back to rule-based SQL
                plan = self.sql_generator.generate(
                    question=question,
                    manifest=manifest,
                    matches=matches,
                    limit=min(request.limit, self.settings.query_row_limit),
                    exact=getattr(request, "exact", False),
                )
                columns, rows = self.duckdb.execute_sql(parquet_path, plan.sql, plan.limit)

        # Step 4: Generate answer — try Claude, fallback to template
        answer = self.response_builder.build(plan, rows)
        if self.claude.available:
            try:
                claude_answer = self.claude.generate_answer(
                    question=question,
                    sql=plan.sql,
                    rows=rows,
                    columns=columns,
                    plan=plan,
                )
                if claude_answer:
                    ai_reasoning = claude_answer
                    answer = claude_answer
            except Exception as exc:
                logger.warning("Claude answer generation failed: %s", exc)

        query_time_ms = round((time.perf_counter() - t_start) * 1000, 1)

        return QueryResponse(
            dataset_id=manifest.dataset_id,
            question=question,
            answer=answer,
            ai_reasoning=ai_reasoning,
            semantic_matches=matches,
            generated_sql=plan,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            query_time_ms=query_time_ms,
            security_audit=security_audit,
        )

    def answer_question_all(self, request: QueryAllRequest) -> QueryResponse:
        question = request.question.strip()
        if not question:
            raise ValueError("Question cannot be empty.")

        t_start = time.perf_counter()

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

        # Step 2: Try Claude for multi-table SQL, fallback to rule-based
        security_audit = {}
        ai_reasoning = ""

        if self.claude.available and not getattr(request, "exact", False):
            try:
                plan, security_audit = self.claude.generate_sql_multi(
                    question=question,
                    manifests=manifests,
                    matches=matches,
                    relation_map=relation_map,
                    limit=min(request.limit, self.settings.query_row_limit),
                )
                logger.info("Claude multi-table SQL generated: %s", plan.sql[:100])
            except Exception as exc:
                logger.warning("Claude multi-table SQL failed, falling back: %s", exc)
                plan = self.multi_sql_generator.generate(
                    question=question,
                    manifests=manifests,
                    matches=matches,
                    relation_map=relation_map,
                    limit=min(request.limit, self.settings.query_row_limit),
                    exact=getattr(request, "exact", False),
                )
        else:
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

        # Step 3: LOCAL SQL execution
        try:
            columns, rows = self.duckdb.execute_sql_many(relation_paths, plan.sql, plan.limit)
        except Exception as sql_exc:
            logger.warning("Multi-table SQL execution failed (%s), attempting Claude fix", sql_exc)
            if self.claude.available:
                try:
                    fixed_plan = self.claude.fix_sql_error(
                        original_sql=plan.sql,
                        error_message=str(sql_exc),
                        limit=plan.limit,
                    )
                    columns, rows = self.duckdb.execute_sql_many(relation_paths, fixed_plan.sql, fixed_plan.limit)
                    plan = fixed_plan
                except Exception:
                    plan = self.multi_sql_generator.generate(
                        question=question,
                        manifests=manifests,
                        matches=matches,
                        relation_map=relation_map,
                        limit=min(request.limit, self.settings.query_row_limit),
                        exact=getattr(request, "exact", False),
                    )
                    columns, rows = self.duckdb.execute_sql_many(relation_paths, plan.sql, plan.limit)
            else:
                plan = self.multi_sql_generator.generate(
                    question=question,
                    manifests=manifests,
                    matches=matches,
                    relation_map=relation_map,
                    limit=min(request.limit, self.settings.query_row_limit),
                    exact=getattr(request, "exact", False),
                )
                columns, rows = self.duckdb.execute_sql_many(relation_paths, plan.sql, plan.limit)

        # Step 4: Generate answer
        answer = self.response_builder.build(plan, rows)
        if self.claude.available:
            try:
                claude_answer = self.claude.generate_answer(
                    question=question,
                    sql=plan.sql,
                    rows=rows,
                    columns=columns,
                    plan=plan,
                )
                if claude_answer:
                    ai_reasoning = claude_answer
                    answer = claude_answer
            except Exception as exc:
                logger.warning("Claude answer generation failed: %s", exc)

        query_time_ms = round((time.perf_counter() - t_start) * 1000, 1)

        return QueryResponse(
            dataset_id="all",
            question=question,
            answer=answer,
            ai_reasoning=ai_reasoning,
            semantic_matches=matches,
            generated_sql=plan,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            query_time_ms=query_time_ms,
            security_audit=security_audit,
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
