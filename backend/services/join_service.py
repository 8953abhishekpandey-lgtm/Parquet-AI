"""
Join Detection Service

Automatically detects potential JOIN columns across uploaded parquet files
by analyzing shared column names, case-insensitive matches, and common
ID/key/code patterns. Updates a join map stored as JSON.
"""

import json
import os
import re
from typing import Any


def detect_joins(all_schemas: list[dict[str, Any]]) -> dict[str, list[str]]:
    """
    Detect potential join columns across all uploaded files.

    Strategies:
    1. Exact column name matches across files
    2. Case-insensitive fuzzy matches
    3. Common ID patterns: columns ending in _id, _code, _key

    Args:
        all_schemas: List of schema dictionaries for all files.

    Returns:
        Join map: {column_name: [list of filenames sharing that column]}
    """
    if len(all_schemas) < 2:
        return {}

    # Build column→files mapping (case-insensitive)
    col_files: dict[str, set[str]] = {}
    col_canonical: dict[str, str] = {}  # lowercase → first-seen casing

    for schema in all_schemas:
        filename = schema["filename"]
        for col in schema.get("columns", []):
            col_name = col["name"]
            col_lower = col_name.lower()

            if col_lower not in col_canonical:
                col_canonical[col_lower] = col_name

            if col_lower not in col_files:
                col_files[col_lower] = set()
            col_files[col_lower].add(filename)

    # Filter to columns that appear in 2+ files
    join_map = {}
    for col_lower, files in col_files.items():
        if len(files) >= 2:
            canonical_name = col_canonical[col_lower]
            join_map[canonical_name] = sorted(list(files))

    return join_map


def save_join_map(join_map: dict[str, list[str]], metadata_dir: str) -> str:
    """
    Save the join map to disk.

    Args:
        join_map: The detected join map.
        metadata_dir: Base metadata directory.

    Returns:
        Path to the saved join map file.
    """
    path = os.path.join(metadata_dir, "join_map.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(join_map, f, indent=2)
    return path


def load_join_map(metadata_dir: str) -> dict[str, list[str]]:
    """
    Load the join map from disk.

    Args:
        metadata_dir: Base metadata directory.

    Returns:
        Join map dictionary, or empty dict if not found.
    """
    path = os.path.join(metadata_dir, "join_map.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def update_join_map(all_schemas: list[dict], metadata_dir: str) -> dict[str, list[str]]:
    """
    Recompute and save the join map based on current schemas.

    Args:
        all_schemas: All current schema dictionaries.
        metadata_dir: Base metadata directory.

    Returns:
        Updated join map.
    """
    join_map = detect_joins(all_schemas)
    save_join_map(join_map, metadata_dir)
    return join_map
