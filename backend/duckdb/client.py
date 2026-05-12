from __future__ import annotations

import math
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from backend.core.config import get_settings


NUMERIC_MARKERS = (
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "HUGEINT",
    "UTINYINT",
    "USMALLINT",
    "UINTEGER",
    "UBIGINT",
    "FLOAT",
    "DOUBLE",
    "DECIMAL",
    "REAL",
)
DATE_MARKERS = ("DATE", "TIME", "TIMESTAMP")


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def safe_relation_name(name: str, index: int) -> str:
    stem = Path(name).stem
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_").lower()
    if not cleaned:
        cleaned = "dataset"
    if not cleaned[0].isalpha():
        cleaned = f"dataset_{cleaned}"
    return f"t{index}_{cleaned}"


def is_numeric_dtype(dtype: str) -> bool:
    upper = dtype.upper()
    return any(marker in upper for marker in NUMERIC_MARKERS)


def is_datetime_dtype(dtype: str) -> bool:
    upper = dtype.upper()
    return any(marker in upper for marker in DATE_MARKERS)


def serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "item"):
        return serialize_value(value.item())
    return value


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        records.append({key: serialize_value(value) for key, value in row.items()})
    return records


class DuckDBAnalytics:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(database=":memory:", read_only=False)

    def _create_view(self, conn: duckdb.DuckDBPyConnection, parquet_path: str | Path) -> None:
        path_literal = quote_literal(str(parquet_path))
        conn.execute(f"CREATE OR REPLACE VIEW dataset AS SELECT * FROM read_parquet({path_literal})")

    def create_relation_map(self, manifests: list[Any]) -> dict[str, str]:
        relation_map: dict[str, str] = {}
        used: set[str] = set()
        for index, manifest in enumerate(manifests):
            base = safe_relation_name(manifest.filename, index)
            relation = base
            suffix = 2
            while relation in used:
                relation = f"{base}_{suffix}"
                suffix += 1
            used.add(relation)
            relation_map[manifest.dataset_id] = relation
        return relation_map

    def inspect_parquet(self, parquet_path: str | Path) -> dict[str, Any]:
        with self._connect() as conn:
            self._create_view(conn, parquet_path)
            desc_df = conn.execute("DESCRIBE dataset").fetchdf()
            row_count = conn.execute("SELECT COUNT(*) AS row_count FROM dataset").fetchone()[0]
            sample_df = conn.execute(f"SELECT * FROM dataset LIMIT {self.settings.sample_rows}").fetchdf()
            sample_rows = dataframe_to_records(sample_df)

            columns = []
            for _, row in desc_df.iterrows():
                name = str(row["column_name"])
                dtype = str(row["column_type"])
                nullable = str(row.get("null", "YES")).upper() != "NO"
                sample_values = self._sample_values(conn, name)
                stats = self._profile_column(conn, name, dtype)
                columns.append(
                    {
                        "name": name,
                        "dtype": dtype,
                        "nullable": nullable,
                        "sample_values": sample_values,
                        "stats": stats,
                    }
                )

        return {
            "row_count": int(row_count),
            "columns": columns,
            "sample_rows": sample_rows,
        }

    def execute_sql(self, parquet_path: str | Path, sql: str, row_limit: int) -> tuple[list[str], list[dict[str, Any]]]:
        cleaned_sql = sql.strip().rstrip(";")
        if not cleaned_sql.lower().startswith(("select", "with")):
            raise ValueError("Generated SQL must be a SELECT or WITH query.")

        with self._connect() as conn:
            self._create_view(conn, parquet_path)
            limited_sql = f"SELECT * FROM ({cleaned_sql}) AS generated_result LIMIT {int(row_limit)}"
            df = conn.execute(limited_sql).fetchdf()

        return list(df.columns), dataframe_to_records(df)

    def execute_sql_many(
        self,
        relation_paths: dict[str, str | Path],
        sql: str,
        row_limit: int,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        cleaned_sql = sql.strip().rstrip(";")
        if not cleaned_sql.lower().startswith(("select", "with")):
            raise ValueError("Generated SQL must be a SELECT or WITH query.")

        with self._connect() as conn:
            for relation_name, parquet_path in relation_paths.items():
                path_literal = quote_literal(str(parquet_path))
                relation_ref = quote_identifier(relation_name)
                conn.execute(
                    f"CREATE OR REPLACE VIEW {relation_ref} AS "
                    f"SELECT * FROM read_parquet({path_literal})"
                )
            limited_sql = f"SELECT * FROM ({cleaned_sql}) AS generated_result LIMIT {int(row_limit)}"
            df = conn.execute(limited_sql).fetchdf()

        return list(df.columns), dataframe_to_records(df)

    def _sample_values(self, conn: duckdb.DuckDBPyConnection, column_name: str) -> list[Any]:
        column = quote_identifier(column_name)
        sql = (
            f"SELECT {column} AS value "
            "FROM dataset "
            f"WHERE {column} IS NOT NULL "
            f"LIMIT {self.settings.profile_top_values}"
        )
        try:
            df = conn.execute(sql).fetchdf()
            return [serialize_value(value) for value in df["value"].tolist()]
        except Exception:
            return []

    def _profile_column(self, conn: duckdb.DuckDBPyConnection, column_name: str, dtype: str) -> dict[str, Any]:
        column = quote_identifier(column_name)
        stats: dict[str, Any] = {}

        try:
            base = conn.execute(
                f"""
                SELECT
                    COUNT(*) - COUNT({column}) AS null_count,
                    COUNT(DISTINCT {column}) AS distinct_count
                FROM dataset
                """
            ).fetchone()
            stats["null_count"] = int(base[0])
            stats["distinct_count"] = int(base[1])
        except Exception:
            stats["null_count"] = None
            stats["distinct_count"] = None

        if is_numeric_dtype(dtype):
            try:
                numeric = conn.execute(
                    f"""
                    SELECT
                        MIN({column}) AS min_value,
                        MAX({column}) AS max_value,
                        AVG({column}) AS avg_value,
                        STDDEV_POP({column}) AS stddev_value
                    FROM dataset
                    WHERE {column} IS NOT NULL
                    """
                ).fetchone()
                stats.update(
                    {
                        "min_value": serialize_value(numeric[0]),
                        "max_value": serialize_value(numeric[1]),
                        "avg_value": serialize_value(numeric[2]),
                        "stddev_value": serialize_value(numeric[3]),
                    }
                )
            except Exception:
                pass
        elif is_datetime_dtype(dtype):
            try:
                bounds = conn.execute(
                    f"""
                    SELECT MIN({column}) AS min_value, MAX({column}) AS max_value
                    FROM dataset
                    WHERE {column} IS NOT NULL
                    """
                ).fetchone()
                stats.update(
                    {
                        "min_value": serialize_value(bounds[0]),
                        "max_value": serialize_value(bounds[1]),
                    }
                )
            except Exception:
                pass
        else:
            try:
                top_df = conn.execute(
                    f"""
                    SELECT CAST({column} AS VARCHAR) AS value, COUNT(*) AS count
                    FROM dataset
                    WHERE {column} IS NOT NULL
                    GROUP BY {column}
                    ORDER BY count DESC
                    LIMIT {self.settings.profile_top_values}
                    """
                ).fetchdf()
                stats["top_values"] = dataframe_to_records(top_df)
            except Exception:
                pass

        return stats
