from __future__ import annotations

import re

from backend.duckdb.client import is_datetime_dtype, is_numeric_dtype, quote_identifier, quote_literal
from backend.models import ColumnProfile, DatasetManifest, GeneratedSQL, SemanticMatch

UNLIMITED = 999_999_999


def _limit_clause(limit: int) -> str:
    """Return a LIMIT clause only when a finite limit is requested."""
    if limit >= UNLIMITED:
        return ""
    return f"\nLIMIT {int(limit)}"


class RuleBasedSQLGenerator:
    def generate(
        self,
        question: str,
        manifest: DatasetManifest,
        matches: list[SemanticMatch],
        limit: int,
        exact: bool = False,
    ) -> GeneratedSQL:
        normalized_question = question.lower()
        # Special-case: count meters per HES within a single dataset
        if self._has_any(normalized_question, ("how many", "number of", "count")) and "hes" in normalized_question:
            hes_column = next(
                (col for col in manifest.columns if "hes" in col.name.lower() or "hes" in col.normalized_name),
                None,
            )
            if hes_column:
                return self._count_sql(hes_column, limit)
        if exact:
            # return exact rows for the dataset; attempt to detect an identifier (e.g., 'meter id CRYT3000295')
            id_match = re.search(r"meter\s*(?:id)?\s*[:#\-]?\s*([A-Za-z0-9\-]{4,})", question, flags=re.IGNORECASE)
            where_clause = ""
            if id_match:
                id_value = id_match.group(1)
                # prefer columns with sample values matching id
                candidates = [c.name for c in manifest.columns if any(str(v) == id_value for v in (c.sample_values or []))]
                if not candidates:
                    candidates = [c.name for c in manifest.columns if "id" in c.name.lower() or "meter" in c.name.lower() or "hes" in c.name.lower() or "device" in c.name.lower()]
                if candidates:
                    literal_col = quote_identifier(candidates[0])
                    # use CAST to VARCHAR to avoid numeric coercion errors
                    where_clause = f"WHERE CAST({literal_col} AS VARCHAR) = {quote_literal(id_value)}"

            selected_names = [column.name for column in manifest.columns]
            sql = f"SELECT * FROM dataset {where_clause}{_limit_clause(limit)}".strip()
            return GeneratedSQL(
                sql=sql,
                intent="exact_preview",
                aggregation=None,
                metric_column=None,
                group_by_columns=[],
                selected_columns=selected_names,
                limit=limit,
                explanation="Returns exact rows for the uploaded dataset.",
            )
        ranked_columns = self._ranked_columns(matches)
        metric = self._choose_metric(normalized_question, manifest.columns, ranked_columns)
        dimension = self._choose_dimension(normalized_question, manifest.columns, ranked_columns, metric)
        time_column = self._choose_time_column(manifest.columns, ranked_columns)

        if self._has_any(normalized_question, ("abnormal", "anomaly", "anomalies", "outlier", "outliers", "unusual")):
            return self._outlier_sql(metric, dimension, manifest, limit)

        if self._has_any(normalized_question, ("trend", "monthly", "daily", "weekly", "yearly", "over time", "timeline")):
            return self._trend_sql(normalized_question, metric, dimension, time_column, limit)

        if self._has_any(normalized_question, ("how many", "number of", "count", "records", "rows")):
            return self._count_sql(dimension, limit)

        if self._has_any(normalized_question, ("highest", "top", "maximum", "max", "most", "largest", "greatest")):
            return self._rank_sql(metric, dimension, "MAX", "DESC", "highest", limit)

        if self._has_any(normalized_question, ("lowest", "bottom", "minimum", "min", "least", "smallest")):
            return self._rank_sql(metric, dimension, "MIN", "ASC", "lowest", limit)

        if self._has_any(normalized_question, ("average", "avg", "mean")):
            if dimension or self._has_any(normalized_question, (" by ", " per ", "each", "compare", "across")):
                return self._group_metric_sql(metric, dimension, "AVG", "average", limit)
            return self._single_metric_sql(metric, "AVG", "average", limit)

        if self._has_any(normalized_question, ("total", "sum", "overall")):
            if dimension:
                return self._group_metric_sql(metric, dimension, "SUM", "total", limit)
            return self._single_metric_sql(metric, "SUM", "total", limit)

        if dimension and metric:
            return self._group_metric_sql(metric, dimension, "AVG", "average", limit)

        return self._select_sql(manifest.columns, ranked_columns, limit)

    def _ranked_columns(self, matches: list[SemanticMatch]) -> list[str]:
        seen: set[str] = set()
        columns: list[str] = []
        for match in matches:
            if match.column_name and match.column_name not in seen:
                seen.add(match.column_name)
                columns.append(match.column_name)
        return columns

    def _choose_metric(
        self,
        question: str,
        columns: list[ColumnProfile],
        ranked_columns: list[str],
    ) -> ColumnProfile | None:
        numeric = [column for column in columns if is_numeric_dtype(column.dtype)]
        if not numeric:
            return None

        for name in ranked_columns:
            column = self._find_column(columns, name)
            if column and is_numeric_dtype(column.dtype):
                return column

        for column in numeric:
            tokens = set(column.normalized_name.split())
            if any(token in question for token in tokens):
                return column

        return numeric[0]

    def _choose_dimension(
        self,
        question: str,
        columns: list[ColumnProfile],
        ranked_columns: list[str],
        metric: ColumnProfile | None,
    ) -> ColumnProfile | None:
        metric_name = metric.name if metric else None
        dimension_candidates = [
            column
            for column in columns
            if column.name != metric_name and not is_numeric_dtype(column.dtype)
        ]
        if not dimension_candidates:
            return None

        for name in ranked_columns:
            column = self._find_column(columns, name)
            if column and column.name != metric_name and not is_numeric_dtype(column.dtype):
                return column

        by_target = self._extract_group_hint(question)
        if by_target:
            for column in dimension_candidates:
                if by_target in column.normalized_name or column.normalized_name in by_target:
                    return column

        low_cardinality = sorted(
            dimension_candidates,
            key=lambda column: column.stats.get("distinct_count") or 10**9,
        )
        return low_cardinality[0]

    def _choose_time_column(self, columns: list[ColumnProfile], ranked_columns: list[str]) -> ColumnProfile | None:
        for name in ranked_columns:
            column = self._find_column(columns, name)
            if column and is_datetime_dtype(column.dtype):
                return column
        for column in columns:
            if is_datetime_dtype(column.dtype):
                return column
        return None

    def _rank_sql(
        self,
        metric: ColumnProfile | None,
        dimension: ColumnProfile | None,
        aggregation: str,
        direction: str,
        label: str,
        limit: int,
    ) -> GeneratedSQL:
        if metric is None:
            return self._count_sql(dimension, limit)

        metric_ref = quote_identifier(metric.name)
        if dimension:
            dimension_ref = quote_identifier(dimension.name)
            sql = (f"""
SELECT
  {dimension_ref} AS {quote_identifier(dimension.name)},
  {aggregation}({metric_ref}) AS metric_value
FROM dataset
WHERE {metric_ref} IS NOT NULL AND {dimension_ref} IS NOT NULL
GROUP BY {dimension_ref}
ORDER BY metric_value {direction}
""" + _limit_clause(limit)).strip()
            return GeneratedSQL(
                sql=sql,
                intent=f"{label}_by_dimension",
                aggregation=aggregation,
                metric_column=metric.name,
                group_by_columns=[dimension.name],
                selected_columns=[dimension.name, metric.name],
                limit=limit,
                explanation=f"Ranks {dimension.name} by {aggregation.lower()} of {metric.name}.",
            )

        sql = f"""
SELECT {aggregation}({metric_ref}) AS metric_value
FROM dataset
WHERE {metric_ref} IS NOT NULL
""".strip()
        return GeneratedSQL(
            sql=sql,
            intent=label,
            aggregation=aggregation,
            metric_column=metric.name,
            group_by_columns=[],
            selected_columns=[metric.name],
            limit=limit,
            explanation=f"Calculates the {label} value of {metric.name}.",
        )

    def _single_metric_sql(
        self,
        metric: ColumnProfile | None,
        aggregation: str,
        label: str,
        limit: int,
    ) -> GeneratedSQL:
        if metric is None:
            return self._count_sql(None, limit)
        metric_ref = quote_identifier(metric.name)
        sql = f"""
SELECT {aggregation}({metric_ref}) AS metric_value
FROM dataset
WHERE {metric_ref} IS NOT NULL
""".strip()
        return GeneratedSQL(
            sql=sql,
            intent=label,
            aggregation=aggregation,
            metric_column=metric.name,
            group_by_columns=[],
            selected_columns=[metric.name],
            limit=limit,
            explanation=f"Calculates {aggregation.lower()} for {metric.name}.",
        )

    def _group_metric_sql(
        self,
        metric: ColumnProfile | None,
        dimension: ColumnProfile | None,
        aggregation: str,
        label: str,
        limit: int,
    ) -> GeneratedSQL:
        if metric is None:
            return self._count_sql(dimension, limit)
        if dimension is None:
            return self._single_metric_sql(metric, aggregation, label, limit)

        metric_ref = quote_identifier(metric.name)
        dimension_ref = quote_identifier(dimension.name)
        sql = (f"""
SELECT
  {dimension_ref} AS {quote_identifier(dimension.name)},
  {aggregation}({metric_ref}) AS metric_value
FROM dataset
WHERE {metric_ref} IS NOT NULL AND {dimension_ref} IS NOT NULL
GROUP BY {dimension_ref}
ORDER BY metric_value DESC
""" + _limit_clause(limit)).strip()
        return GeneratedSQL(
            sql=sql,
            intent=f"{label}_by_dimension",
            aggregation=aggregation,
            metric_column=metric.name,
            group_by_columns=[dimension.name],
            selected_columns=[dimension.name, metric.name],
            limit=limit,
            explanation=f"Groups by {dimension.name} and computes {aggregation.lower()} of {metric.name}.",
        )

    def _trend_sql(
        self,
        question: str,
        metric: ColumnProfile | None,
        dimension: ColumnProfile | None,
        time_column: ColumnProfile | None,
        limit: int,
    ) -> GeneratedSQL:
        if metric is None:
            return self._count_sql(dimension, limit)
        if time_column is None:
            return self._group_metric_sql(metric, dimension, "AVG", "trend_fallback", limit)

        bucket = "month"
        if "daily" in question:
            bucket = "day"
        elif "weekly" in question:
            bucket = "week"
        elif "yearly" in question or "annual" in question:
            bucket = "year"

        aggregation = "AVG" if self._has_any(question, ("average", "avg", "mean")) else "SUM"
        metric_ref = quote_identifier(metric.name)
        time_ref = quote_identifier(time_column.name)
        group_fields = ["period"]
        selected = [time_column.name, metric.name]
        dimension_select = ""
        dimension_group = ""
        dimension_order = ""

        if dimension and self._has_any(question, ("compare", "by", "across", "per")):
            dimension_ref = quote_identifier(dimension.name)
            dimension_select = f",\n  {dimension_ref} AS {quote_identifier(dimension.name)}"
            dimension_group = f", {dimension_ref}"
            dimension_order = f", {dimension_ref}"
            group_fields.append(dimension.name)
            selected.append(dimension.name)

        sql = (f"""
SELECT
  DATE_TRUNC('{bucket}', {time_ref}) AS period{dimension_select},
  {aggregation}({metric_ref}) AS metric_value
FROM dataset
WHERE {time_ref} IS NOT NULL AND {metric_ref} IS NOT NULL
GROUP BY period{dimension_group}
ORDER BY period{dimension_order}
""" + _limit_clause(limit)).strip()
        return GeneratedSQL(
            sql=sql,
            intent=f"{bucket}_trend",
            aggregation=aggregation,
            metric_column=metric.name,
            group_by_columns=group_fields,
            selected_columns=selected,
            limit=limit,
            explanation=f"Builds a {bucket} trend using {aggregation.lower()} of {metric.name}.",
        )

    def _outlier_sql(
        self,
        metric: ColumnProfile | None,
        dimension: ColumnProfile | None,
        manifest: DatasetManifest,
        limit: int,
    ) -> GeneratedSQL:
        if metric is None:
            return self._select_sql(manifest.columns, [], limit)

        metric_ref = quote_identifier(metric.name)
        display_columns: list[ColumnProfile] = []
        if dimension:
            display_columns.append(dimension)
        display_columns.extend(
            column
            for column in manifest.columns
            if column.name != metric.name and column.name not in {item.name for item in display_columns}
        )
        display_columns = display_columns[:3]
        select_prefix = ""
        selected_columns = [metric.name]
        if display_columns:
            select_prefix = ",\n  ".join(f"{quote_identifier(column.name)} AS {quote_identifier(column.name)}" for column in display_columns)
            select_prefix += ",\n  "
            selected_columns = [column.name for column in display_columns] + [metric.name]

        sql = (f"""
WITH stats AS (
  SELECT AVG({metric_ref}) AS mean_value, STDDEV_POP({metric_ref}) AS std_value
  FROM dataset
  WHERE {metric_ref} IS NOT NULL
),
scored AS (
  SELECT
    *,
    CASE
      WHEN stats.std_value IS NULL OR stats.std_value = 0 THEN 0
      ELSE ABS(({metric_ref} - stats.mean_value) / stats.std_value)
    END AS z_score
  FROM dataset, stats
  WHERE {metric_ref} IS NOT NULL
)
SELECT
  {select_prefix}{metric_ref} AS {quote_identifier(metric.name)},
  z_score
FROM scored
WHERE z_score >= 2
ORDER BY z_score DESC
""" + _limit_clause(limit)).strip()
        return GeneratedSQL(
            sql=sql,
            intent="outlier_detection",
            aggregation="Z_SCORE",
            metric_column=metric.name,
            group_by_columns=[dimension.name] if dimension else [],
            selected_columns=selected_columns,
            limit=limit,
            explanation=f"Finds possible abnormal rows using z-score on {metric.name}.",
        )

    def _count_sql(self, dimension: ColumnProfile | None, limit: int) -> GeneratedSQL:
        if dimension:
            dimension_ref = quote_identifier(dimension.name)
            sql = (f"""
SELECT
  {dimension_ref} AS {quote_identifier(dimension.name)},
  COUNT(*) AS record_count
FROM dataset
WHERE {dimension_ref} IS NOT NULL
GROUP BY {dimension_ref}
ORDER BY record_count DESC
""" + _limit_clause(limit)).strip()
            return GeneratedSQL(
                sql=sql,
                intent="count_by_dimension",
                aggregation="COUNT",
                metric_column=None,
                group_by_columns=[dimension.name],
                selected_columns=[dimension.name],
                limit=limit,
                explanation=f"Counts records grouped by {dimension.name}.",
            )

        sql = "SELECT COUNT(*) AS record_count FROM dataset"
        return GeneratedSQL(
            sql=sql,
            intent="count",
            aggregation="COUNT",
            metric_column=None,
            group_by_columns=[],
            selected_columns=[],
            limit=limit,
            explanation="Counts all records in the uploaded parquet file.",
        )

    def _select_sql(self, columns: list[ColumnProfile], ranked_columns: list[str], limit: int) -> GeneratedSQL:
        selected = [name for name in ranked_columns if self._find_column(columns, name)]
        if not selected:
            selected = [column.name for column in columns[:8]]
        select_list = ",\n  ".join(f"{quote_identifier(name)} AS {quote_identifier(name)}" for name in selected)
        sql = (f"""
SELECT
  {select_list}
FROM dataset
""" + _limit_clause(limit)).strip()
        return GeneratedSQL(
            sql=sql,
            intent="preview",
            aggregation=None,
            metric_column=None,
            group_by_columns=[],
            selected_columns=selected,
            limit=limit,
            explanation="Returns the most semantically relevant columns as a preview.",
        )

    def _find_column(self, columns: list[ColumnProfile], name: str) -> ColumnProfile | None:
        return next((column for column in columns if column.name == name), None)

    def _extract_group_hint(self, question: str) -> str | None:
        match = re.search(r"\b(?:by|per|across|for each)\s+([a-z0-9_\-\s]+)", question)
        if not match:
            return None
        return match.group(1).strip()

    def _has_any(self, text: str, terms: tuple[str, ...]) -> bool:
        for term in terms:
            if term != term.strip() or " " in term:
                if term in text:
                    return True
                continue
            if re.search(rf"\b{re.escape(term)}\b", text):
                return True
        return False
