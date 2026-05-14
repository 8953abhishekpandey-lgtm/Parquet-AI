"""
Results Route — GET /api/results

Query history and aggregate statistics.
"""

import os
from fastapi import APIRouter

from backend.services.query_history_service import QueryHistoryService

router = APIRouter()


@router.get("/results")
async def get_results():
    """
    Get query history with all past queries and results.

    Returns:
        List of query history entries and aggregate stats.
    """
    metadata_dir = os.getenv("METADATA_DIR", "./metadata")
    history_service = QueryHistoryService(metadata_dir)

    entries = history_service.get_all()
    stats = history_service.get_stats()

    return {
        "queries": entries,
        "stats": stats,
    }


@router.get("/results/{entry_id}")
async def get_result_detail(entry_id: int):
    """
    Get detailed information for a specific query history entry.

    Args:
        entry_id: The history entry ID.

    Returns:
        Full query history entry with results.
    """
    metadata_dir = os.getenv("METADATA_DIR", "./metadata")
    history_service = QueryHistoryService(metadata_dir)

    entry = history_service.get_entry(entry_id)
    if entry is None:
        return {"error": "Entry not found", "detail": f"No entry with ID {entry_id}"}

    return entry


@router.get("/results/stats")
async def get_result_stats():
    """
    Get aggregate query statistics.

    Returns:
        Total queries, average response time, total tokens, success rate.
    """
    metadata_dir = os.getenv("METADATA_DIR", "./metadata")
    history_service = QueryHistoryService(metadata_dir)
    return history_service.get_stats()
