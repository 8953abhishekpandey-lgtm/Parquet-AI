"""
Query Route — POST /api/query

Executes the full text-to-SQL pipeline synchronously:
schema → context → SQL generation → validation → execution → answer
"""

import os
import time
from fastapi import APIRouter, Request, HTTPException

from backend.api.models.query_models import QueryRequest
from backend.services.execution_service import execute_query
from backend.services.query_history_service import QueryHistoryService

router = APIRouter()


@router.post("/query")
async def run_query(request: Request, body: QueryRequest):
    """
    Execute a natural language query against uploaded parquet files.

    Pipeline:
    1. Load all schemas
    2. Detect join opportunities
    3. Build minimal Claude context (schema only, no data)
    4. Generate DuckDB SQL via Claude
    5. Validate SQL for safety
    6. Execute on DuckDB
    7. Generate natural language answer

    Args:
        body: QueryRequest with question and optional file filter.

    Returns:
        QueryResponse with SQL, results, answer, and pipeline steps.
    """
    if not body.question or not body.question.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "Empty question", "detail": "Please provide a question", "step": "input"}
        )

    schema_store = request.app.state.schema_store
    metadata_dir = os.getenv("METADATA_DIR", "./metadata")

    try:
        result = await execute_query(
            question=body.question.strip(),
            schema_store=schema_store,
            metadata_dir=metadata_dir,
            selected_files=body.selected_files,
        )

        # Save to history
        try:
            history_service = QueryHistoryService(metadata_dir)
            history_service.add_entry(result)
        except Exception:
            pass  # Don't fail the query if history save fails

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "Query error", "detail": str(e), "step": "execution"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "Internal error", "detail": str(e), "step": "execution"}
        )
