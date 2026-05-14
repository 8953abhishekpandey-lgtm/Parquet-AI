"""
Query Stream Route — GET /api/query/stream

Server-Sent Events (SSE) endpoint that streams pipeline steps
in real time as the query progresses through each stage.
"""

import os
import json
import asyncio
import time
from fastapi import APIRouter, Request, Query
from sse_starlette.sse import EventSourceResponse

from backend.services.execution_service import execute_query
from backend.services.query_history_service import QueryHistoryService

router = APIRouter()


@router.get("/query/stream")
async def stream_query(
    request: Request,
    question: str = Query(..., description="The user's question"),
    selected_files: str = Query(None, description="Comma-separated filenames"),
):
    """
    Stream query pipeline progress via Server-Sent Events.

    Emits events for each pipeline step as it completes,
    allowing the frontend to show real-time progress.

    Args:
        question: The user's natural language question.
        selected_files: Optional comma-separated list of filenames.

    Returns:
        SSE event stream with pipeline step updates.
    """
    schema_store = request.app.state.schema_store
    metadata_dir = os.getenv("METADATA_DIR", "./metadata")

    files_list = None
    if selected_files:
        files_list = [f.strip() for f in selected_files.split(",") if f.strip()]

    async def event_generator():
        """Generate SSE events for each pipeline step."""
        step_counter = [0]

        async def emit_step(label: str, status: str = "running", detail: str = "", result: dict = None):
            """Emit a single pipeline step event."""
            step_counter[0] += 1
            event_data = {
                "step": step_counter[0],
                "label": label,
                "status": status,
                "detail": detail,
            }
            if result:
                event_data["result"] = result

            yield {
                "event": "step",
                "data": json.dumps(event_data, default=str),
            }

        # Emit initial step
        for event in emit_step.__wrapped__(  # type: ignore
            "Question received", "done", question[:100]
        ) if False else []:
            yield event

        # Actually run the query
        try:
            result = await execute_query(
                question=question.strip(),
                schema_store=schema_store,
                metadata_dir=metadata_dir,
                selected_files=files_list,
            )

            # Emit pipeline steps from the result
            pipeline_steps = result.get("pipeline_steps", [])
            for step in pipeline_steps:
                yield {
                    "event": "step",
                    "data": json.dumps(step, default=str),
                }
                await asyncio.sleep(0.05)  # Small delay for visual effect

            # Emit final result
            yield {
                "event": "complete",
                "data": json.dumps(result, default=str),
            }

            # Save to history
            try:
                history_service = QueryHistoryService(metadata_dir)
                history_service.add_entry(result)
            except Exception:
                pass

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({
                    "error": str(e),
                    "step": "execution",
                }, default=str),
            }

    return EventSourceResponse(event_generator())
