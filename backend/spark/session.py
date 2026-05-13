from pathlib import Path
from typing import Any

from backend.core.config import get_settings


class SparkSchemaReader:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._spark = None

    def inspect(self, parquet_path: str | Path) -> dict[str, Any]:
        if not self.settings.enable_spark_schema:
            return {"available": False, "reason": "Spark schema inspection disabled."}

        try:
            spark = self._get_spark()
            dataframe = spark.read.parquet(str(parquet_path))
            fields = [
                {
                    "name": field.name,
                    "dtype": field.dataType.simpleString(),
                    "nullable": bool(field.nullable),
                }
                for field in dataframe.schema.fields
            ]
            return {
                "available": True,
                "columns": fields,
                "row_count": int(dataframe.count()),
            }
        except Exception as exc:
            return {
                "available": False,
                "error": str(exc),
            }

    def _get_spark(self):
        if self._spark is None:
            from pyspark.sql import SparkSession

            self._spark = (
                SparkSession.builder.appName("local-parquet-schema-reader")
                .master("local[*]")
                .config("spark.sql.execution.arrow.pyspark.enabled", "true")
                .getOrCreate()
            )
            self._spark.sparkContext.setLogLevel("ERROR")
        return self._spark

