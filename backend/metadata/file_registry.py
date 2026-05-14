"""
File Registry — Track uploaded parquet files.

Maintains a JSON registry of all uploaded files with their
metadata (size, upload time, indexing status). Acts as the
source of truth for what files are available for querying.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any


class FileRegistry:
    """Manages the registry of uploaded parquet files."""

    def __init__(self, metadata_dir: str):
        """
        Initialize the file registry.

        Args:
            metadata_dir: Base metadata directory path.
        """
        self.registry_path = os.path.join(metadata_dir, "file_registry.json")
        self._ensure_registry()

    def _ensure_registry(self) -> None:
        """Create registry file if it doesn't exist."""
        if not os.path.exists(self.registry_path):
            self._save_registry({"files": {}})

    def _load_registry(self) -> dict:
        """Load the registry from disk."""
        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"files": {}}

    def _save_registry(self, registry: dict) -> None:
        """Save the registry to disk."""
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, default=str)

    def register_file(
        self,
        filename: str,
        filepath: str,
        file_size_bytes: int,
        row_count: int = 0,
        col_count: int = 0,
    ) -> dict[str, Any]:
        """
        Register a newly uploaded file.

        Args:
            filename: Name of the parquet file.
            filepath: Absolute path to the file.
            file_size_bytes: File size in bytes.
            row_count: Number of rows extracted.
            col_count: Number of columns extracted.

        Returns:
            The file registry entry.
        """
        registry = self._load_registry()

        entry = {
            "filename": filename,
            "filepath": filepath,
            "file_size_bytes": file_size_bytes,
            "file_size_mb": round(file_size_bytes / (1024 * 1024), 2),
            "row_count": row_count,
            "col_count": col_count,
            "status": "indexed",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "last_indexed_at": datetime.now(timezone.utc).isoformat(),
        }

        registry["files"][filename] = entry
        self._save_registry(registry)
        return entry

    def get_file(self, filename: str) -> dict[str, Any] | None:
        """Get a single file entry."""
        registry = self._load_registry()
        return registry["files"].get(filename)

    def get_all_files(self) -> list[dict[str, Any]]:
        """Get all registered files."""
        registry = self._load_registry()
        return list(registry["files"].values())

    def delete_file(self, filename: str) -> bool:
        """
        Remove a file from the registry.

        Args:
            filename: Name of the file to remove.

        Returns:
            True if removed, False if not found.
        """
        registry = self._load_registry()
        if filename in registry["files"]:
            del registry["files"][filename]
            self._save_registry(registry)
            return True
        return False

    def file_exists(self, filename: str) -> bool:
        """Check if a file is registered."""
        registry = self._load_registry()
        return filename in registry["files"]

    def get_file_count(self) -> int:
        """Get the number of registered files."""
        registry = self._load_registry()
        return len(registry["files"])

    def update_file_status(self, filename: str, status: str) -> None:
        """Update the status of a file entry."""
        registry = self._load_registry()
        if filename in registry["files"]:
            registry["files"][filename]["status"] = status
            self._save_registry(registry)
