"""
Health Check Route — GET /api/health

Returns system health status including DuckDB connection,
Anthropic API configuration, and file counts.
"""

import time
from fastapi import APIRouter, Request

from backend.duckdb.connection import health_check as duckdb_health
from backend.anthropic_client.client import api_health_check

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    """
    System health check endpoint.

    Returns:
        Health status for all subsystems.
    """
    start = time.time()

    # DuckDB status
    duckdb_status = duckdb_health()

    # Anthropic API status
    api_status = api_health_check()

    # File count
    file_count = 0
    try:
        file_registry = request.app.state.file_registry
        file_count = file_registry.get_file_count()
    except Exception:
        pass

    # Schema count
    schema_count = 0
    try:
        schema_store = request.app.state.schema_store
        schema_count = len(schema_store.get_all_schemas())
    except Exception:
        pass

    elapsed = int((time.time() - start) * 1000)

    return {
        "status": "healthy" if duckdb_status["status"] == "healthy" else "degraded",
        "response_time_ms": elapsed,
        "duckdb": duckdb_status,
        "anthropic_api": api_status,
        "files_loaded": file_count,
        "schemas_indexed": schema_count,
    }
