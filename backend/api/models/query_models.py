"""
Query Models — Pydantic models for query request/response.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any


class QueryRequest(BaseModel):
    """Request model for submitting a query."""
    question: str = Field(..., description="Natural language question about the data")
    selected_files: Optional[list[str]] = Field(
        None,
        description="Optional list of filenames to restrict the query to"
    )


class PipelineStep(BaseModel):
    """A single step in the query pipeline."""
    step_number: int
    label: str
    status: str = Field(..., description="pending | running | done | error")
    detail: Optional[str] = None
    time_ms: Optional[int] = None


class QueryResponse(BaseModel):
    """Response model for a completed query."""
    question: str
    sql: Optional[str] = None
    raw_results: list[dict[str, Any]] = []
    columns: list[str] = []
    row_count: int = 0
    natural_language_answer: Optional[str] = None
    files_queried: list[str] = []
    execution_time_ms: int = 0
    duckdb_time_ms: int = 0
    sql_attempts: int = 1
    tokens_used: int = 0
    truncated: bool = False
    pipeline_steps: list[dict[str, Any]] = []
    attempts_detail: list[dict[str, Any]] = []
    context_tokens: int = 0
    error: Optional[str] = None


class QueryHistoryEntry(BaseModel):
    """A single entry in query history."""
    id: int
    timestamp: str
    question: str
    sql: Optional[str] = None
    row_count: int = 0
    tokens_used: int = 0
    execution_time_ms: int = 0
    files_queried: list[str] = []
    sql_attempts: int = 1
    natural_language_answer: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


class QueryStats(BaseModel):
    """Aggregate query statistics."""
    total_queries: int = 0
    avg_response_time_ms: int = 0
    total_tokens: int = 0
    success_rate: float = 0.0
