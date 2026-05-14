"""
Schema Extraction Service

Extracts structural metadata from parquet files using PyArrow and DuckDB.
Produces a schema dictionary containing column names, types, sample values,
null percentages, min/max values, and unique counts — but NEVER actual data rows.
"""

import os
from typing import Any

import pyarrow.parquet as pq
from backend.duckdb.connection import get_connection


def extract_schema(filepath: str, filename: str) -> dict[str, Any]:
    """
    Extract schema metadata from a parquet file.

    The extracted schema contains structural information only:
    - Column names and data types
    - 3-5 sample values per column (non-sensitive preview)
    - Null percentages, unique counts, min/max for numeric columns
    - Row and column counts, file size

    Args:
        filepath: Absolute path to the parquet file.
        filename: Original filename.

    Returns:
        Schema dictionary with full structural metadata.

    Raises:
        FileNotFoundError: If the parquet file doesn't exist.
        Exception: If the file cannot be parsed.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    # Read parquet metadata with PyArrow
    pf = pq.ParquetFile(filepath)
    arrow_schema = pf.schema_arrow
    num_rows = pf.metadata.num_rows
    file_size_bytes = os.path.getsize(filepath)

    # Use DuckDB to extract column statistics and samples
    conn = get_connection()

    columns = []
    for i in range(len(arrow_schema)):
        field = arrow_schema.field(i)
        col_name = field.name
        col_type = _arrow_type_to_duckdb_type(str(field.type))

        col_info = {
            "name": col_name,
            "dtype": col_type,
            "null_pct": 0.0,
            "unique_count": 0,
            "sample_values": [],
            "min": None,
            "max": None,
        }

        try:
            # Get null percentage
            null_result = conn.execute(
                f'SELECT (COUNT(*) - COUNT("{col_name}")) * 100.0 / GREATEST(COUNT(*), 1) '
                f"FROM read_parquet('{filepath}')"
            ).fetchone()
            col_info["null_pct"] = round(null_result[0], 1) if null_result else 0.0

            # Get unique count
            unique_result = conn.execute(
                f'SELECT COUNT(DISTINCT "{col_name}") FROM read_parquet(\'{filepath}\')'
            ).fetchone()
            col_info["unique_count"] = unique_result[0] if unique_result else 0

            # Get sample values (up to 5 distinct non-null values)
            sample_result = conn.execute(
                f'SELECT DISTINCT "{col_name}" FROM read_parquet(\'{filepath}\') '
                f'WHERE "{col_name}" IS NOT NULL LIMIT 5'
            ).fetchall()
            col_info["sample_values"] = [
                _serialize_value(row[0]) for row in sample_result
            ]

            # Get min/max for numeric/date types
            if col_type in ("INTEGER", "BIGINT", "DOUBLE", "FLOAT", "DECIMAL", "DATE", "TIMESTAMP"):
                minmax_result = conn.execute(
                    f'SELECT MIN("{col_name}"), MAX("{col_name}") '
                    f"FROM read_parquet('{filepath}')"
                ).fetchone()
                if minmax_result:
                    col_info["min"] = _serialize_value(minmax_result[0])
                    col_info["max"] = _serialize_value(minmax_result[1])

        except Exception:
            # If any column stat fails, keep defaults and continue
            pass

        columns.append(col_info)

    schema = {
        "filename": filename,
        "filepath": filepath,
        "row_count": num_rows,
        "col_count": len(columns),
        "file_size_mb": round(file_size_bytes / (1024 * 1024), 2),
        "columns": columns,
    }

    return schema


def _arrow_type_to_duckdb_type(arrow_type: str) -> str:
    """Map PyArrow type strings to DuckDB type names."""
    type_map = {
        "int8": "TINYINT",
        "int16": "SMALLINT",
        "int32": "INTEGER",
        "int64": "BIGINT",
        "uint8": "UTINYINT",
        "uint16": "USMALLINT",
        "uint32": "UINTEGER",
        "uint64": "UBIGINT",
        "float": "FLOAT",
        "float16": "FLOAT",
        "float32": "FLOAT",
        "double": "DOUBLE",
        "float64": "DOUBLE",
        "string": "VARCHAR",
        "utf8": "VARCHAR",
        "large_string": "VARCHAR",
        "large_utf8": "VARCHAR",
        "bool": "BOOLEAN",
        "boolean": "BOOLEAN",
        "date32": "DATE",
        "date32[day]": "DATE",
        "date64": "DATE",
        "timestamp[ns]": "TIMESTAMP",
        "timestamp[us]": "TIMESTAMP",
        "timestamp[ms]": "TIMESTAMP",
        "timestamp[s]": "TIMESTAMP",
        "binary": "BLOB",
        "large_binary": "BLOB",
    }

    arrow_lower = arrow_type.lower().strip()
    # Check exact match first
    if arrow_lower in type_map:
        return type_map[arrow_lower]

    # Check prefix matches
    for prefix, dtype in type_map.items():
        if arrow_lower.startswith(prefix):
            return dtype

    # Check for decimal
    if "decimal" in arrow_lower:
        return "DECIMAL"

    return "VARCHAR"  # fallback


def _serialize_value(val: Any) -> Any:
    """Ensure a value is JSON-serializable."""
    if val is None:
        return None
    if isinstance(val, (int, float, str, bool)):
        return val
    if hasattr(val, "isoformat"):
        return val.isoformat()
    if isinstance(val, (bytes, bytearray)):
        return val.hex()
    return str(val)
