"""
File Models — Pydantic models for file upload/management.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any


class FileInfo(BaseModel):
    """Information about an uploaded file."""
    filename: str
    filepath: str
    file_size_bytes: int = 0
    file_size_mb: float = 0.0
    row_count: int = 0
    col_count: int = 0
    status: str = "indexed"
    uploaded_at: Optional[str] = None
    last_indexed_at: Optional[str] = None


class UploadResponse(BaseModel):
    """Response model for file upload."""
    filename: str
    status: str
    schema: Optional[dict[str, Any]] = None
    join_map: Optional[dict[str, list[str]]] = None
    pipeline_steps: list[dict[str, Any]] = []
    error: Optional[str] = None


class SchemaResponse(BaseModel):
    """Response model for schema query."""
    filename: str
    filepath: str
    row_count: int = 0
    col_count: int = 0
    file_size_mb: float = 0.0
    columns: list[dict[str, Any]] = []


class JoinMapResponse(BaseModel):
    """Response model for join map query."""
    join_map: dict[str, list[str]] = {}
    total_join_columns: int = 0
