from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    nullable: bool = True
    normalized_name: str
    sample_values: list[Any] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    semantic_text: str = ""


class DatasetManifest(BaseModel):
    dataset_id: str
    filename: str
    stored_path: str
    uploaded_at: datetime
    row_count: int
    columns: list[ColumnProfile]
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    spark_schema: dict[str, Any] = Field(default_factory=dict)
    metadata_count: int = 0


class UploadResponse(BaseModel):
    dataset: DatasetManifest


class UploadFailure(BaseModel):
    filename: str
    error: str


class MultiUploadResponse(BaseModel):
    datasets: list[DatasetManifest] = Field(default_factory=list)
    errors: list[UploadFailure] = Field(default_factory=list)


class QueryRequest(BaseModel):
    dataset_id: str
    question: str
    limit: int = Field(default=100, ge=1, le=500)
    exact: bool = False


class QueryAllRequest(BaseModel):
    question: str
    dataset_ids: list[str] | None = None
    limit: int = Field(default=100, ge=1, le=500)
    exact: bool = False


class SemanticMatch(BaseModel):
    score: float
    kind: str
    column_name: str | None = None
    text: str
    payload: dict[str, Any] = Field(default_factory=dict)


class GeneratedSQL(BaseModel):
    sql: str
    intent: str
    aggregation: str | None = None
    metric_column: str | None = None
    group_by_columns: list[str] = Field(default_factory=list)
    selected_columns: list[str] = Field(default_factory=list)
    limit: int
    explanation: str


class QueryResponse(BaseModel):
    dataset_id: str
    question: str
    answer: str
    ai_reasoning: str = ""
    semantic_matches: list[SemanticMatch]
    generated_sql: GeneratedSQL
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    security_audit: dict[str, Any] = Field(default_factory=lambda: {
        "data_sent_to_api": {},
        "data_kept_local": {
            "full_parquet_file": True,
            "all_row_data": True,
            "embeddings": True,
            "vector_database": True,
            "sql_execution": True,
        },
        "raw_data_sent": False,
        "full_dataset_sent": False,
    })
