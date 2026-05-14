"""
Query History Service — Store and retrieve past query results.

Maintains a local JSON file of all query history entries for
the Results page and Debug page.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any

MAX_HISTORY = 200  # Keep last 200 queries


class QueryHistoryService:
    """Manages local query history storage."""

    def __init__(self, metadata_dir: str):
        """
        Initialize the query history service.

        Args:
            metadata_dir: Base metadata directory path.
        """
        self.history_path = os.path.join(metadata_dir, "query_history.json")
        self._ensure_history()

    def _ensure_history(self) -> None:
        """Create history file if it doesn't exist."""
        if not os.path.exists(self.history_path):
            self._save_history({"queries": []})

    def _load_history(self) -> dict:
        """Load history from disk."""
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"queries": []}

    def _save_history(self, history: dict) -> None:
        """Save history to disk."""
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, default=str)

    def add_entry(self, query_result: dict[str, Any]) -> dict[str, Any]:
        """
        Add a query result to history.

        Args:
            query_result: The complete query response dictionary.

        Returns:
            The history entry with an added ID and timestamp.
        """
        history = self._load_history()

        entry = {
            "id": len(history["queries"]) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "question": query_result.get("question", ""),
            "sql": query_result.get("sql", ""),
            "row_count": query_result.get("row_count", 0),
            "tokens_used": query_result.get("tokens_used", 0),
            "execution_time_ms": query_result.get("execution_time_ms", 0),
            "files_queried": query_result.get("files_queried", []),
            "sql_attempts": query_result.get("sql_attempts", 1),
            "natural_language_answer": query_result.get("natural_language_answer", ""),
            "success": "error" not in query_result or query_result.get("error") is None,
            "error": query_result.get("error"),
            "raw_results": query_result.get("raw_results", [])[:20],  # Store max 20 rows
            "columns": query_result.get("columns", []),
            "pipeline_steps": query_result.get("pipeline_steps", []),
            "attempts_detail": query_result.get("attempts_detail", []),
            "context_tokens": query_result.get("context_tokens", 0),
            "duckdb_time_ms": query_result.get("duckdb_time_ms", 0),
        }

        history["queries"].append(entry)

        # Trim to MAX_HISTORY
        if len(history["queries"]) > MAX_HISTORY:
            history["queries"] = history["queries"][-MAX_HISTORY:]

        self._save_history(history)
        return entry

    def get_all(self) -> list[dict[str, Any]]:
        """Get all history entries, newest first."""
        history = self._load_history()
        return list(reversed(history["queries"]))

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        """Get a specific history entry by ID."""
        history = self._load_history()
        for entry in history["queries"]:
            if entry.get("id") == entry_id:
                return entry
        return None

    def get_stats(self) -> dict[str, Any]:
        """
        Get aggregate statistics about query history.

        Returns:
            Dictionary with total queries, avg time, total tokens, success rate.
        """
        history = self._load_history()
        queries = history["queries"]

        if not queries:
            return {
                "total_queries": 0,
                "avg_response_time_ms": 0,
                "total_tokens": 0,
                "success_rate": 0.0,
            }

        total = len(queries)
        total_time = sum(q.get("execution_time_ms", 0) for q in queries)
        total_tokens = sum(q.get("tokens_used", 0) for q in queries)
        successes = sum(1 for q in queries if q.get("success", False))

        return {
            "total_queries": total,
            "avg_response_time_ms": int(total_time / total) if total else 0,
            "total_tokens": total_tokens,
            "success_rate": round((successes / total) * 100, 1) if total else 0.0,
        }

    def clear_history(self) -> None:
        """Clear all query history."""
        self._save_history({"queries": []})
