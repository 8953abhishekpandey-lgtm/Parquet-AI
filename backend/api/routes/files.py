"""
Files Route — GET /api/files, DELETE /api/files/{filename}

Manage uploaded parquet files: list, delete, re-index.
"""

import os
from fastapi import APIRouter, Request, HTTPException

from backend.services.schema_service import extract_schema
from backend.services.join_service import update_join_map

router = APIRouter()


@router.get("/files")
async def list_files(request: Request):
    """
    List all uploaded and indexed parquet files.

    Returns:
        List of file info dictionaries.
    """
    file_registry = request.app.state.file_registry
    files = file_registry.get_all_files()
    return {"files": files, "count": len(files)}


@router.delete("/files/{filename}")
async def delete_file(request: Request, filename: str):
    """
    Delete an uploaded parquet file and its associated metadata.

    Args:
        filename: The parquet filename to delete.

    Returns:
        Confirmation of deletion.
    """
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    metadata_dir = os.getenv("METADATA_DIR", "./metadata")
    filepath = os.path.join(upload_dir, filename)

    # Delete physical file
    if os.path.exists(filepath):
        os.remove(filepath)

    # Delete schema
    schema_store = request.app.state.schema_store
    schema_store.delete_schema(filename)

    # Remove from registry
    file_registry = request.app.state.file_registry
    removed = file_registry.delete_file(filename)

    if not removed:
        raise HTTPException(
            status_code=404,
            detail={"error": "File not found", "detail": f"'{filename}' not in registry"}
        )

    # Update join map after deletion
    all_schemas = schema_store.get_all_schemas()
    update_join_map(all_schemas, metadata_dir)

    return {"status": "deleted", "filename": filename}


@router.post("/files/{filename}/reindex")
async def reindex_file(request: Request, filename: str):
    """
    Re-extract schema for an existing file.

    Args:
        filename: The parquet filename to re-index.

    Returns:
        Updated schema information.
    """
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    metadata_dir = os.getenv("METADATA_DIR", "./metadata")
    filepath = os.path.abspath(os.path.join(upload_dir, filename))

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=404,
            detail={"error": "File not found", "detail": f"'{filename}' not on disk"}
        )

    try:
        schema = extract_schema(filepath, filename)

        schema_store = request.app.state.schema_store
        schema_store.save_schema(filename, schema)

        file_registry = request.app.state.file_registry
        file_registry.register_file(
            filename=filename,
            filepath=filepath,
            file_size_bytes=os.path.getsize(filepath),
            row_count=schema["row_count"],
            col_count=schema["col_count"],
        )

        # Update join map
        all_schemas = schema_store.get_all_schemas()
        join_map = update_join_map(all_schemas, metadata_dir)

        return {
            "status": "reindexed",
            "filename": filename,
            "schema": schema,
            "join_map": join_map,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "Re-index failed", "detail": str(e)}
        )
