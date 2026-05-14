"""
Upload Route — POST /api/upload

Handles parquet file uploads with a full processing pipeline:
1. Save file to uploads directory
2. Extract schema metadata
3. Register file in registry
4. Detect join opportunities
5. Return schema + join map
"""

import os
import time
from fastapi import APIRouter, UploadFile, File, Request, HTTPException

from backend.services.schema_service import extract_schema
from backend.services.join_service import update_join_map

router = APIRouter()


@router.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """
    Upload and process a parquet file.

    The file is saved locally, its schema is extracted (columns, types,
    sample values, stats), registered in the file index, and join
    opportunities are detected across all uploaded files.

    Args:
        file: The uploaded parquet file.

    Returns:
        Upload response with schema, join map, and pipeline steps.
    """
    start = time.time()
    pipeline_steps = []

    # Validate file type
    if not file.filename or not file.filename.endswith(".parquet"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid file type",
                "detail": "Only .parquet files are accepted",
                "step": "upload",
            }
        )

    filename = file.filename
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    metadata_dir = os.getenv("METADATA_DIR", "./metadata")
    filepath = os.path.abspath(os.path.join(upload_dir, filename))

    # Step 1: Save file
    step_start = time.time()
    try:
        os.makedirs(upload_dir, exist_ok=True)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        file_size = len(content)
        pipeline_steps.append({
            "step": 1,
            "label": "File uploaded",
            "status": "done",
            "detail": f"{filename} ({file_size / (1024*1024):.1f} MB)",
            "time_ms": int((time.time() - step_start) * 1000),
        })
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "Upload failed", "detail": str(e), "step": "upload"}
        )

    # Step 2: Extract schema
    step_start = time.time()
    try:
        schema = extract_schema(filepath, filename)
        pipeline_steps.append({
            "step": 2,
            "label": "Schema extracted",
            "status": "done",
            "detail": f"{schema['col_count']} columns detected",
            "time_ms": int((time.time() - step_start) * 1000),
        })
    except Exception as e:
        # Clean up uploaded file on schema failure
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Schema extraction failed",
                "detail": str(e),
                "step": "schema_extraction",
            }
        )

    # Step 3: Save schema + register file
    step_start = time.time()
    try:
        schema_store = request.app.state.schema_store
        schema_store.save_schema(filename, schema)

        file_registry = request.app.state.file_registry
        file_registry.register_file(
            filename=filename,
            filepath=filepath,
            file_size_bytes=file_size,
            row_count=schema["row_count"],
            col_count=schema["col_count"],
        )
        pipeline_steps.append({
            "step": 3,
            "label": "Stats computed",
            "status": "done",
            "detail": f"{schema['row_count']:,} rows",
            "time_ms": int((time.time() - step_start) * 1000),
        })
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "Registration failed", "detail": str(e), "step": "registration"}
        )

    # Step 4: Detect joins
    step_start = time.time()
    try:
        all_schemas = schema_store.get_all_schemas()
        join_map = update_join_map(all_schemas, metadata_dir)
        join_detail = "No shared columns detected"
        if join_map:
            cols = list(join_map.keys())[:3]
            join_detail = f"{', '.join(cols)} shared across files"
        pipeline_steps.append({
            "step": 4,
            "label": "Join scan complete",
            "status": "done",
            "detail": join_detail,
            "time_ms": int((time.time() - step_start) * 1000),
        })
    except Exception as e:
        join_map = {}
        pipeline_steps.append({
            "step": 4,
            "label": "Join scan",
            "status": "error",
            "detail": str(e)[:80],
            "time_ms": int((time.time() - step_start) * 1000),
        })

    # Step 5: Ready
    total_time = int((time.time() - start) * 1000)
    pipeline_steps.append({
        "step": 5,
        "label": "Ready",
        "status": "done",
        "detail": f"Indexed in {total_time}ms",
        "time_ms": total_time,
    })

    return {
        "filename": filename,
        "status": "indexed",
        "schema": schema,
        "join_map": join_map,
        "pipeline_steps": pipeline_steps,
        "execution_time_ms": total_time,
    }
