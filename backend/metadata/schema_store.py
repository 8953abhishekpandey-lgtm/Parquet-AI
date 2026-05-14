"""
Schema Store — Local JSON storage for parquet schema metadata.

Stores extracted schema information (column names, types, sample values,
statistics) as JSON files. No actual data rows are stored — only structural
metadata that is safe to share with Claude API.
"""

import json
import os
from typing import Any


class SchemaStore:
    """Manages local JSON schema files for uploaded parquet files."""

    def __init__(self, metadata_dir: str):
        """
        Initialize the schema store.

        Args:
            metadata_dir: Base metadata directory path.
        """
        self.schemas_dir = os.path.join(metadata_dir, "schemas")
        os.makedirs(self.schemas_dir, exist_ok=True)

    def save_schema(self, filename: str, schema: dict[str, Any]) -> str:
        """
        Save schema metadata for a parquet file.

        Args:
            filename: The parquet filename (e.g., "sales.parquet").
            schema: Schema dictionary with columns, types, samples, etc.

        Returns:
            Path to the saved schema JSON file.
        """
        safe_name = filename.replace(".parquet", "").replace(" ", "_")
        schema_path = os.path.join(self.schemas_dir, f"{safe_name}.json")

        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2, default=str)

        return schema_path

    def get_schema(self, filename: str) -> dict[str, Any] | None:
        """
        Load schema metadata for a specific file.

        Args:
            filename: The parquet filename.

        Returns:
            Schema dictionary or None if not found.
        """
        safe_name = filename.replace(".parquet", "").replace(" ", "_")
        schema_path = os.path.join(self.schemas_dir, f"{safe_name}.json")

        if not os.path.exists(schema_path):
            return None

        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """
        Load all stored schemas.

        Returns:
            List of all schema dictionaries.
        """
        schemas = []
        if not os.path.exists(self.schemas_dir):
            return schemas

        for file in sorted(os.listdir(self.schemas_dir)):
            if file.endswith(".json"):
                filepath = os.path.join(self.schemas_dir, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        schemas.append(json.load(f))
                except (json.JSONDecodeError, IOError):
                    continue

        return schemas

    def delete_schema(self, filename: str) -> bool:
        """
        Delete schema metadata for a file.

        Args:
            filename: The parquet filename.

        Returns:
            True if deleted, False if not found.
        """
        safe_name = filename.replace(".parquet", "").replace(" ", "_")
        schema_path = os.path.join(self.schemas_dir, f"{safe_name}.json")

        if os.path.exists(schema_path):
            os.remove(schema_path)
            return True
        return False

    def schema_exists(self, filename: str) -> bool:
        """Check if schema exists for a given file."""
        safe_name = filename.replace(".parquet", "").replace(" ", "_")
        schema_path = os.path.join(self.schemas_dir, f"{safe_name}.json")
        return os.path.exists(schema_path)
