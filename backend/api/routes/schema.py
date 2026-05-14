"""
Schema Route — GET /api/schema/{filename}

Returns schema metadata for a specific file or all files.
Also provides the join map for cross-file relationships.
"""

import os
from fastapi import APIRouter, Request, HTTPException

from backend.services.join_service import load_join_map

router = APIRouter()


@router.get("/schema")
async def get_all_schemas(request: Request):
    """
    Get schema metadata for all uploaded files.

    Returns:
        List of all schema dictionaries + join map.
    """
    schema_store = request.app.state.schema_store
    metadata_dir = os.getenv("METADATA_DIR", "./metadata")

    all_schemas = schema_store.get_all_schemas()
    join_map = load_join_map(metadata_dir)

    return {
        "schemas": all_schemas,
        "join_map": join_map,
        "total_files": len(all_schemas),
        "total_columns": sum(s.get("col_count", 0) for s in all_schemas),
        "total_rows": sum(s.get("row_count", 0) for s in all_schemas),
    }


@router.get("/schema/{filename}")
async def get_file_schema(request: Request, filename: str):
    """
    Get schema metadata for a specific file.

    Args:
        filename: The parquet filename.

    Returns:
        Schema dictionary for the file.
    """
    schema_store = request.app.state.schema_store
    schema = schema_store.get_schema(filename)

    if schema is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Schema not found", "detail": f"No schema for '{filename}'"}
        )

    return schema
