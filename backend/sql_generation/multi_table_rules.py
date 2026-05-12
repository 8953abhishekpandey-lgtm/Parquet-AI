from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backend.duckdb.client import is_datetime_dtype, is_numeric_dtype, quote_identifier, quote_literal
from backend.models import ColumnProfile, DatasetManifest, GeneratedSQL, SemanticMatch


@dataclass(frozen=True)
class TableRef:
    dataset_id: str
    filename: str
    label: str
    relation: str
    manifest: DatasetManifest


@dataclass(frozen=True)
class ColumnRef:
    table: TableRef
    column: ColumnProfile

    @property
    def key(self) -> tuple[str, str]:
        return (self.table.dataset_id, self.column.name)

    @property
    def label(self) -> str:
        return f"{self.table.label}.{self.column.name}"


@dataclass(frozen=True)
class JoinEdge:
    left: TableRef
    left_column: ColumnProfile
    right: TableRef
    right_column: ColumnProfile
    confidence: float
    reason: str


class MultiTableSQLGenerator:
    def generate(
        self,
        question: str,
        manifests: list[DatasetManifest],
        matches: list[SemanticMatch],
        relation_map: dict[str, str],
        limit: int,
        exact: bool = False,
    ) -> GeneratedSQL:
        if not manifests:
            raise ValueError("No uploaded parquet datasets are available.")

        question_lc = question.lower()
        tables = self._tables(manifests, relation_map)
        columns = [ColumnRef(table, column) for table in tables for column in table.manifest.columns]
        matched_scores = self._matched_scores(matches)
        active_tables = self._active_tables(question_lc, tables, matches)
        edges = self._infer_join_edges(tables)

        metric = self._choose_metric(question_lc, columns, matched_scores)
        dimension = self._choose_dimension(question_lc, columns, matched_scores, metric)
        time_column = self._choose_time_column(question_lc, columns, matched_scores)

        selected_tables = self._selected_tables(active_tables, metric, dimension, time_column)
        join_plan = self._join_plan(selected_tables, edges, metric, dimension, time_column)

        # ── exact row lookup ──────────────────────────────────────────────
        if exact:
            tables_j, joins_j = join_plan
            if not tables_j:
                tables_j = active_tables[:1]
                joins_j = []
            aliases = self._aliases(tables_j)
            from_clause = self._from_clause(tables_j, joins_j, aliases)

            # Explicit per-column aliases to avoid DuckDB auto-renaming
            # (ID -> ID_1, ID_2 ...) when multiple tables share column names.
            select_items: list[str] = []
            seen_names: set[str] = set()
            for tref in tables_j:
                alias = aliases[tref.dataset_id]
                for col in tref.manifest.columns:
                    display = (
                        col.name
                        if col.name not in seen_names
                        else f"{tref.label}__{col.name}"
                    )
                    seen_names.add(display)
                    select_items.append(
                        f"{alias}.{quote_identifier(col.name)} AS {quote_identifier(display)}"
                    )
            select_list = ",\n  ".join(select_items)

            id_value = self._extract_identifier_from_question(question)
            where_clause = (
                "\n" + self._build_id_where_clause(id_value, tables_j, aliases)
                if id_value
                else ""
            )
            sql = f"SELECT\n  {select_list}\n{from_clause}{where_clause}\nLIMIT {int(limit)}"
            return GeneratedSQL(
                sql=sql,
                intent="exact_preview",
                aggregation=None,
                metric_column=None,
                group_by_columns=[],
                selected_columns=[],
                limit=limit,
                explanation="Returns exact rows for the selected/joined uploaded datasets.",
            )

        # ── count queries ─────────────────────────────────────────────────
        if self._has_any(question_lc, ("how many", "number of", "count", "records", "rows")):
            if self._has_any(
                question_lc,
                ("all", "each", "every", "files", "datasets", "tables", "uploaded"),
            ):
                return self._count_all_sql(active_tables, limit)
            # count grouped by a dimension, e.g. "count meters per hes"
            return self._count_by_dimension_sql(dimension, join_plan, active_tables, limit)

        # ── intent routing ────────────────────────────────────────────────
        if self._has_any(question_lc, ("abnormal", "anomaly", "anomalies", "outlier", "outliers", "unusual")):
            if metric:
                return self._outlier_sql(metric, dimension, columns, matched_scores, join_plan, limit)
            return self._preview_sql(question_lc, columns, matched_scores, active_tables, join_plan, limit)

        if self._has_any(question_lc, ("trend", "monthly", "daily", "weekly", "yearly", "over time", "timeline")):
            if metric and time_column:
                return self._trend_sql(question_lc, metric, dimension, time_column, join_plan, limit)
            return self._preview_sql(question_lc, columns, matched_scores, active_tables, join_plan, limit)

        if self._has_any(question_lc, ("highest", "top", "maximum", "max", "most", "largest", "greatest")):
            if metric and dimension:
                return self._group_metric_sql(metric, dimension, "MAX", "highest", join_plan, limit)
            return self._preview_sql(question_lc, columns, matched_scores, active_tables, join_plan, limit, metric, "DESC")

        if self._has_any(question_lc, ("lowest", "bottom", "minimum", "min", "least", "smallest")):
            if metric and dimension:
                return self._group_metric_sql(metric, dimension, "MIN", "lowest", join_plan, limit)
            return self._preview_sql(question_lc, columns, matched_scores, active_tables, join_plan, limit, metric, "ASC")

        if self._has_any(question_lc, ("average", "avg", "mean")) and metric:
            if dimension:
                return self._group_metric_sql(metric, dimension, "AVG", "average", join_plan, limit)
            return self._single_metric_sql(metric, "AVG", "average", limit)

        if self._has_any(question_lc, ("total", "sum", "overall")) and metric:
            if dimension:
                return self._group_metric_sql(metric, dimension, "SUM", "total", join_plan, limit)
            return self._single_metric_sql(metric, "SUM", "total", limit)

        return self._preview_sql(question_lc, columns, matched_scores, active_tables, join_plan, limit)

    # ── table / column helpers ────────────────────────────────────────────

    def _tables(self, manifests: list[DatasetManifest], relation_map: dict[str, str]) -> list[TableRef]:
        return [
            TableRef(
                dataset_id=manifest.dataset_id,
                filename=manifest.filename,
                label=Path(manifest.filename).stem,
                relation=relation_map[manifest.dataset_id],
                manifest=manifest,
            )
            for manifest in manifests
        ]

    def _matched_scores(self, matches: list[SemanticMatch]) -> dict[tuple[str, str], float]:
        scores: dict[tuple[str, str], float] = {}
        for match in matches:
            dataset_id = match.payload.get("dataset_id")
            if dataset_id and match.column_name:
                key = (str(dataset_id), match.column_name)
                scores[key] = max(scores.get(key, 0.0), match.score)
        return scores

    def _active_tables(
        self,
        question: str,
        tables: list[TableRef],
        matches: list[SemanticMatch],
    ) -> list[TableRef]:
        if self._has_any(
            question,
            ("all", "every", "uploaded", "files", "datasets", "tables", "join", "combined", "complete"),
        ):
            return tables

        dataset_scores: dict[str, float] = {}
        for match in matches:
            dataset_id = match.payload.get("dataset_id")
            if dataset_id:
                dataset_scores[str(dataset_id)] = dataset_scores.get(str(dataset_id), 0.0) + match.score

        if not dataset_scores:
            return tables

        selected_ids = {
            did
            for did, _ in sorted(dataset_scores.items(), key=lambda x: x[1], reverse=True)[:4]
        }
        return [t for t in tables if t.dataset_id in selected_ids] or tables

    def _selected_tables(
        self,
        active_tables: list[TableRef],
        metric: ColumnRef | None,
        dimension: ColumnRef | None,
        time_column: ColumnRef | None,
    ) -> list[TableRef]:
        selected: list[TableRef] = list(active_tables)
        for ref in (metric, dimension, time_column):
            if ref and ref.table not in selected:
                selected.append(ref.table)
        return selected

    # ── column scoring ────────────────────────────────────────────────────

    def _choose_metric(
        self,
        question: str,
        columns: list[ColumnRef],
        matched_scores: dict[tuple[str, str], float],
    ) -> ColumnRef | None:
        numeric = [ref for ref in columns if is_numeric_dtype(ref.column.dtype)]
        if not numeric:
            return None

        scored = []
        for ref in numeric:
            score = matched_scores.get(ref.key, 0.0) * 5
            score += self._question_overlap(question, ref.column.normalized_name) * 2
            score += self._question_overlap(question, ref.table.label.lower())
            distinct = ref.column.stats.get("distinct_count")
            if distinct and distinct > 1:
                score += 0.5
            if distinct == 1:
                score -= 1.5
            if self._is_key_or_audit_column(ref.column.name):
                score -= 4.0
            scored.append((score, ref))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_ref = scored[0]
        if best_score <= -2 and any(not self._is_key_or_audit_column(r.column.name) for r in numeric):
            return next(r for _, r in scored if not self._is_key_or_audit_column(r.column.name))
        return best_ref

    def _choose_dimension(
        self,
        question: str,
        columns: list[ColumnRef],
        matched_scores: dict[tuple[str, str], float],
        metric: ColumnRef | None,
    ) -> ColumnRef | None:
        candidates = [
            ref for ref in columns
            if ref.key != (metric.key if metric else None)
            and not is_datetime_dtype(ref.column.dtype)
            and not self._is_audit_column(ref.column.name)
        ]
        if not candidates:
            return None

        scored = []
        for ref in candidates:
            score = matched_scores.get(ref.key, 0.0) * 5
            score += self._question_overlap(question, ref.column.normalized_name) * 2
            score += self._question_overlap(question, ref.table.label.lower())
            if not is_numeric_dtype(ref.column.dtype):
                score += 0.75
            if self._is_key_or_audit_column(ref.column.name):
                score -= 2.5
            distinct = ref.column.stats.get("distinct_count")
            if distinct and 1 < distinct <= 1000:
                score += 0.4
            scored.append((score, ref))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def _choose_time_column(
        self,
        question: str,
        columns: list[ColumnRef],
        matched_scores: dict[tuple[str, str], float],
    ) -> ColumnRef | None:
        candidates = [ref for ref in columns if is_datetime_dtype(ref.column.dtype)]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda ref: matched_scores.get(ref.key, 0.0) * 5
            + self._question_overlap(question, ref.column.normalized_name),
        )

    # ── join inference ────────────────────────────────────────────────────

    def _infer_join_edges(self, tables: list[TableRef]) -> list[JoinEdge]:
        edges: list[JoinEdge] = []
        for left in tables:
            for right in tables:
                if left.dataset_id == right.dataset_id:
                    continue
                for left_col in left.manifest.columns:
                    for right_col in right.manifest.columns:
                        confidence, reason = self._join_confidence(left, left_col, right, right_col)
                        if confidence > 0:
                            edges.append(JoinEdge(left, left_col, right, right_col, confidence, reason))

        unique: dict[tuple[str, str], JoinEdge] = {}
        for edge in edges:
            pair = tuple(sorted((edge.left.dataset_id, edge.right.dataset_id)))
            current = unique.get(pair)
            if current is None or edge.confidence > current.confidence:
                unique[pair] = edge
        return sorted(unique.values(), key=lambda e: e.confidence, reverse=True)

    def _join_confidence(
        self,
        left: TableRef,
        left_col: ColumnProfile,
        right: TableRef,
        right_col: ColumnProfile,
    ) -> tuple[float, str]:
        left_name = self._compact(left_col.name)
        right_name = self._compact(right_col.name)
        left_table = self._compact(left.label)
        right_table = self._compact(right.label)
        right_table_light = self._light_table_name(right.label)

        if not self._is_joinable(left_col, right_col):
            return 0.0, ""

        if left_name == right_name and left_name not in {"id", "createdby", "changedby"}:
            return 0.65, f"same column name {left_col.name}"

        if left_name.endswith("id") and left_name != "id":
            prefix = left_name[:-2]
            if prefix and (prefix in right_table or prefix in right_table_light or right_table_light in prefix):
                if right_name == "id":
                    return 0.95, f"{left_col.name} references {right.label}.ID"
                if right_name == "utilityid":
                    return 0.86, f"{left_col.name} references {right.label}.Utility_ID"

        if right_name.endswith("id") and right_name != "id":
            prefix = right_name[:-2]
            left_table_light = self._light_table_name(left.label)
            if prefix and (prefix in left_table or prefix in left_table_light or left_table_light in prefix):
                if left_name == "id":
                    return 0.95, f"{right_col.name} references {left.label}.ID"
                if left_name == "utilityid":
                    return 0.86, f"{right_col.name} references {left.label}.Utility_ID"

        return 0.0, ""

    def _join_plan(
        self,
        selected_tables: list[TableRef],
        edges: list[JoinEdge],
        metric: ColumnRef | None,
        dimension: ColumnRef | None,
        time_column: ColumnRef | None,
    ) -> tuple[list[TableRef], list[JoinEdge]]:
        if not selected_tables:
            return [], []

        base = self._best_base_table(selected_tables, edges, metric, dimension, time_column)
        joined = [base]
        joins: list[JoinEdge] = []
        pending = {t.dataset_id for t in selected_tables if t.dataset_id != base.dataset_id}

        while pending:
            joined_ids = {t.dataset_id for t in joined}
            crossing = [
                edge for edge in edges
                if (edge.left.dataset_id in joined_ids and edge.right.dataset_id in pending)
                or (edge.right.dataset_id in joined_ids and edge.left.dataset_id in pending)
            ]
            if not crossing:
                break
            edge = max(crossing, key=lambda e: e.confidence)
            joins.append(edge)
            next_table = edge.right if edge.left.dataset_id in joined_ids else edge.left
            joined.append(next_table)
            pending.remove(next_table.dataset_id)

        return joined, joins

    def _best_base_table(
        self,
        selected_tables: list[TableRef],
        edges: list[JoinEdge],
        metric: ColumnRef | None,
        dimension: ColumnRef | None,
        time_column: ColumnRef | None,
    ) -> TableRef:
        important = [ref.table for ref in (metric, dimension, time_column) if ref]
        candidates = (important + selected_tables) if important else selected_tables

        def score(table: TableRef) -> float:
            degree = sum(
                1 for e in edges
                if e.left.dataset_id == table.dataset_id or e.right.dataset_id == table.dataset_id
            )
            return degree * 10 + min(table.manifest.row_count or 0, 1_000_000) / 1_000_000

        return max(candidates, key=score)

    # ── SQL builders ──────────────────────────────────────────────────────

    def _count_all_sql(self, tables: list[TableRef], limit: int) -> GeneratedSQL:
        selects = [
            f"SELECT {quote_literal(t.filename)} AS dataset_name, COUNT(*) AS record_count "
            f"FROM {quote_identifier(t.relation)}"
            for t in tables
        ]
        sql = "\nUNION ALL\n".join(selects) + "\nORDER BY record_count DESC"
        return GeneratedSQL(
            sql=sql,
            intent="multi_dataset_counts",
            aggregation="COUNT",
            metric_column=None,
            group_by_columns=["dataset_name"],
            selected_columns=["dataset_name", "record_count"],
            limit=limit,
            explanation="Counts rows in each uploaded parquet dataset.",
        )

    def _count_by_dimension_sql(
        self,
        dimension: ColumnRef | None,
        join_plan: tuple[list[TableRef], list[JoinEdge]],
        active_tables: list[TableRef],
        limit: int,
    ) -> GeneratedSQL:
        # No dimension resolved — fall back to per-table counts
        if dimension is None:
            return self._count_all_sql(join_plan[0] or active_tables, limit)

        tables, joins = self._ensure_tables_for_refs(join_plan, [dimension])
        aliases = self._aliases(tables)
        from_clause = self._from_clause(tables, joins, aliases)
        dimension_expr = self._column_expr(dimension, aliases)

        sql = f"""
SELECT
  {dimension_expr} AS {quote_identifier(dimension.label)},
  COUNT(*) AS record_count
{from_clause}
WHERE {dimension_expr} IS NOT NULL
GROUP BY {dimension_expr}
ORDER BY record_count DESC
LIMIT {int(limit)}
""".strip()

        return GeneratedSQL(
            sql=sql,
            intent="multi_count_by_dimension",
            aggregation="COUNT",
            metric_column=None,
            group_by_columns=[dimension.label],
            selected_columns=[dimension.label, "record_count"],
            limit=limit,
            explanation=f"Counts records grouped by {dimension.label}.",
        )

    def _group_metric_sql(
        self,
        metric: ColumnRef,
        dimension: ColumnRef,
        aggregation: str,
        label: str,
        join_plan: tuple[list[TableRef], list[JoinEdge]],
        limit: int,
    ) -> GeneratedSQL:
        tables, joins = self._ensure_tables_for_refs(join_plan, [metric, dimension])
        aliases = self._aliases(tables)
        from_clause = self._from_clause(tables, joins, aliases)
        metric_expr = self._column_expr(metric, aliases)
        dimension_expr = self._column_expr(dimension, aliases)

        sql = f"""
SELECT
  {dimension_expr} AS {quote_identifier(dimension.label)},
  {aggregation}({metric_expr}) AS metric_value
{from_clause}
WHERE {metric_expr} IS NOT NULL AND {dimension_expr} IS NOT NULL
GROUP BY {dimension_expr}
ORDER BY metric_value DESC
LIMIT {int(limit)}
""".strip()

        return GeneratedSQL(
            sql=sql,
            intent=f"multi_{label}_by_dimension",
            aggregation=aggregation,
            metric_column=metric.label,
            group_by_columns=[dimension.label],
            selected_columns=[dimension.label, metric.label],
            limit=limit,
            explanation=f"Joins matching datasets and groups {dimension.label} by {aggregation.lower()} of {metric.label}.",
        )

    def _single_metric_sql(self, metric: ColumnRef, aggregation: str, label: str, limit: int) -> GeneratedSQL:
        alias = "t0"
        metric_expr = f"{alias}.{quote_identifier(metric.column.name)}"
        sql = f"""
SELECT {aggregation}({metric_expr}) AS metric_value
FROM {quote_identifier(metric.table.relation)} AS {alias}
WHERE {metric_expr} IS NOT NULL
""".strip()
        return GeneratedSQL(
            sql=sql,
            intent=f"multi_{label}",
            aggregation=aggregation,
            metric_column=metric.label,
            group_by_columns=[],
            selected_columns=[metric.label],
            limit=limit,
            explanation=f"Calculates {aggregation.lower()} for {metric.label}.",
        )

    def _trend_sql(
        self,
        question: str,
        metric: ColumnRef,
        dimension: ColumnRef | None,
        time_column: ColumnRef,
        join_plan: tuple[list[TableRef], list[JoinEdge]],
        limit: int,
    ) -> GeneratedSQL:
        refs = [metric, time_column] + ([dimension] if dimension else [])
        tables, joins = self._ensure_tables_for_refs(join_plan, refs)
        aliases = self._aliases(tables)
        from_clause = self._from_clause(tables, joins, aliases)
        metric_expr = self._column_expr(metric, aliases)
        time_expr = self._column_expr(time_column, aliases)

        bucket = "month"
        if "daily" in question:
            bucket = "day"
        elif "weekly" in question:
            bucket = "week"
        elif "yearly" in question or "annual" in question:
            bucket = "year"

        aggregation = "AVG" if self._has_any(question, ("average", "avg", "mean")) else "SUM"
        dimension_select = dimension_group = dimension_order = ""
        groups = ["period"]
        selected = [time_column.label, metric.label]

        if dimension and dimension.table.dataset_id in aliases:
            dimension_expr = self._column_expr(dimension, aliases)
            dimension_select = f",\n  {dimension_expr} AS {quote_identifier(dimension.label)}"
            dimension_group = f", {dimension_expr}"
            dimension_order = f", {dimension_expr}"
            groups.append(dimension.label)
            selected.append(dimension.label)

        sql = f"""
SELECT
  DATE_TRUNC('{bucket}', {time_expr}) AS period{dimension_select},
  {aggregation}({metric_expr}) AS metric_value
{from_clause}
WHERE {time_expr} IS NOT NULL AND {metric_expr} IS NOT NULL
GROUP BY period{dimension_group}
ORDER BY period{dimension_order}
LIMIT {int(limit)}
""".strip()

        return GeneratedSQL(
            sql=sql,
            intent=f"multi_{bucket}_trend",
            aggregation=aggregation,
            metric_column=metric.label,
            group_by_columns=groups,
            selected_columns=selected,
            limit=limit,
            explanation=f"Builds a {bucket} trend across joined datasets using {metric.label}.",
        )

    def _outlier_sql(
        self,
        metric: ColumnRef,
        dimension: ColumnRef | None,
        columns: list[ColumnRef],
        matched_scores: dict[tuple[str, str], float],
        join_plan: tuple[list[TableRef], list[JoinEdge]],
        limit: int,
    ) -> GeneratedSQL:
        display_refs = [
            ref for ref in self._display_columns(columns, matched_scores, join_plan[0], metric, max_columns=8)
            if ref.key != metric.key
        ]
        if dimension and dimension not in display_refs:
            display_refs.insert(0, dimension)

        tables, joins = self._ensure_tables_for_refs(join_plan, [metric] + display_refs)
        aliases = self._aliases(tables)
        from_clause = self._from_clause(tables, joins, aliases)
        metric_expr = self._column_expr(metric, aliases)
        base_from = from_clause.strip()

        select_items = [
            f"{self._column_expr(ref, aliases)} AS {quote_identifier(ref.label)}"
            for ref in display_refs
            if ref.table.dataset_id in aliases
        ]
        select_items.append(f"{metric_expr} AS {quote_identifier(metric.label)}")
        scored_select = ",\n    ".join(select_items)
        scored_from = f"  {base_from}\n  CROSS JOIN stats"

        sql = f"""
WITH stats AS (
  SELECT
    AVG({metric_expr}) AS mean_value,
    STDDEV_POP({metric_expr}) AS std_value
  {base_from}
  WHERE {metric_expr} IS NOT NULL
),
scored AS (
  SELECT
    {scored_select},
    CASE
      WHEN stats.std_value IS NULL OR stats.std_value = 0 THEN 0
      ELSE ABS(({metric_expr} - stats.mean_value) / stats.std_value)
    END AS z_score
  {scored_from}
  WHERE {metric_expr} IS NOT NULL
)
SELECT *
FROM scored
WHERE z_score >= 2
ORDER BY z_score DESC
LIMIT {int(limit)}
""".strip()

        return GeneratedSQL(
            sql=sql,
            intent="multi_outlier_detection",
            aggregation="Z_SCORE",
            metric_column=metric.label,
            group_by_columns=[dimension.label] if dimension else [],
            selected_columns=[ref.label for ref in display_refs] + [metric.label, "z_score"],
            limit=limit,
            explanation=f"Searches uploaded datasets and finds possible abnormal rows using z-score on {metric.label}.",
        )

    def _preview_sql(
        self,
        question: str,
        columns: list[ColumnRef],
        matched_scores: dict[tuple[str, str], float],
        active_tables: list[TableRef],
        join_plan: tuple[list[TableRef], list[JoinEdge]],
        limit: int,
        order_metric: ColumnRef | None = None,
        order_direction: str = "DESC",
    ) -> GeneratedSQL:
        tables, joins = join_plan
        if not tables:
            tables = active_tables[:1]
            joins = []
        selected_refs = self._display_columns(columns, matched_scores, tables, order_metric, max_columns=18)
        if order_metric and order_metric not in selected_refs:
            selected_refs.append(order_metric)
        tables, joins = self._ensure_tables_for_refs((tables, joins), selected_refs)
        aliases = self._aliases(tables)
        from_clause = self._from_clause(tables, joins, aliases)
        selected_refs = [ref for ref in selected_refs if ref.table.dataset_id in aliases]
        select_list = ",\n  ".join(
            f"{self._column_expr(ref, aliases)} AS {quote_identifier(ref.label)}"
            for ref in selected_refs
        )
        order_clause = self._order_clause(question, selected_refs, aliases, order_metric, order_direction)
        sql = f"""
SELECT
  {select_list}
{from_clause}
{order_clause}
LIMIT {int(limit)}
""".strip()

        return GeneratedSQL(
            sql=sql,
            intent="multi_dataset_join_preview" if joins else "multi_dataset_preview",
            aggregation=None,
            metric_column=order_metric.label if order_metric else None,
            group_by_columns=[],
            selected_columns=[ref.label for ref in selected_refs],
            limit=limit,
            explanation=(
                "Returns semantically relevant columns from joined uploaded datasets."
                if joins
                else "Returns semantically relevant columns from the best matching uploaded dataset."
            ),
        )

    # ── display column selection ──────────────────────────────────────────

    def _display_columns(
        self,
        columns: list[ColumnRef],
        matched_scores: dict[tuple[str, str], float],
        tables: list[TableRef],
        metric: ColumnRef | None,
        max_columns: int,
    ) -> list[ColumnRef]:
        table_ids = {t.dataset_id for t in tables}
        candidates = [
            ref for ref in columns
            if ref.table.dataset_id in table_ids and not self._is_audit_column(ref.column.name)
        ]

        def score(ref: ColumnRef) -> float:
            value = matched_scores.get(ref.key, 0.0) * 5
            if ref == metric:
                value += 2
            if self._is_key_or_audit_column(ref.column.name):
                value -= 1
            if not is_numeric_dtype(ref.column.dtype):
                value += 0.4
            return value

        ranked = sorted(candidates, key=score, reverse=True)
        selected: list[ColumnRef] = []
        for ref in ranked:
            if ref not in selected:
                selected.append(ref)
            if len(selected) >= max_columns:
                break
        return selected or candidates[:max_columns]

    # ── FROM / alias / expression helpers ────────────────────────────────

    def _ensure_tables_for_refs(
        self,
        join_plan: tuple[list[TableRef], list[JoinEdge]],
        refs: list[ColumnRef],
    ) -> tuple[list[TableRef], list[JoinEdge]]:
        tables, joins = join_plan
        if tables:
            return tables, joins
        fallback: list[TableRef] = []
        for ref in refs:
            if ref.table not in fallback:
                fallback.append(ref.table)
        return fallback, []

    def _from_clause(
        self,
        tables: list[TableRef],
        joins: list[JoinEdge],
        aliases: dict[str, str],
    ) -> str:
        base = tables[0]
        lines = [f"FROM {quote_identifier(base.relation)} AS {aliases[base.dataset_id]}"]
        joined = {base.dataset_id}
        for edge in joins:
            if edge.left.dataset_id in joined and edge.right.dataset_id not in joined:
                new_table = edge.right
                left_alias = aliases[edge.left.dataset_id]
                right_alias = aliases[edge.right.dataset_id]
            elif edge.right.dataset_id in joined and edge.left.dataset_id not in joined:
                new_table = edge.left
                left_alias = aliases[edge.left.dataset_id]
                right_alias = aliases[edge.right.dataset_id]
            else:
                continue
            on_clause = (
                f"{left_alias}.{quote_identifier(edge.left_column.name)} = "
                f"{right_alias}.{quote_identifier(edge.right_column.name)}"
            )
            lines.append(
                f"LEFT JOIN {quote_identifier(new_table.relation)} AS {aliases[new_table.dataset_id]} "
                f"ON {on_clause}"
            )
            joined.add(new_table.dataset_id)
        return "\n" + "\n".join(lines)

    def _aliases(self, tables: list[TableRef]) -> dict[str, str]:
        return {t.dataset_id: f"t{i}" for i, t in enumerate(tables)}

    def _column_expr(self, ref: ColumnRef, aliases: dict[str, str]) -> str:
        return f"{aliases[ref.table.dataset_id]}.{quote_identifier(ref.column.name)}"

    def _order_clause(
        self,
        question: str,
        refs: list[ColumnRef],
        aliases: dict[str, str],
        metric: ColumnRef | None,
        direction: str,
    ) -> str:
        if metric and metric.table.dataset_id in aliases:
            return f"ORDER BY {self._column_expr(metric, aliases)} {direction}"
        if self._has_any(question, ("latest", "recent", "newest")):
            time_ref = next((ref for ref in refs if is_datetime_dtype(ref.column.dtype)), None)
            if time_ref:
                return f"ORDER BY {self._column_expr(time_ref, aliases)} DESC"
        id_ref = next((ref for ref in refs if self._compact(ref.column.name) == "id"), None)
        if id_ref:
            return f"ORDER BY {self._column_expr(id_ref, aliases)}"
        return ""

    # ── identifier extraction ─────────────────────────────────────────────

    def _extract_identifier_from_question(self, question: str) -> str | None:
        m = re.search(r"meter\s*(?:id)?\s*[:#\-]?\s*([A-Za-z0-9\-]{4,})", question, flags=re.IGNORECASE)
        return m.group(1) if m else None

    def _build_id_where_clause(self, id_value: str, tables: list[TableRef], aliases: dict[str, str]) -> str:
        candidates: list[tuple[str, str]] = []
        for table in tables:
            alias = aliases[table.dataset_id]
            for col in table.manifest.columns:
                samples = col.sample_values or []
                if any(str(v) == id_value for v in samples):
                    candidates.append((alias, col.name))

        if not candidates:
            for table in tables:
                alias = aliases[table.dataset_id]
                for col in table.manifest.columns:
                    name_l = col.name.lower()
                    if any(k in name_l for k in ("id", "meter", "hes", "device", "code")) or name_l.endswith("cd"):
                        candidates.append((alias, col.name))

        if not candidates:
            return ""

        literal = quote_literal(id_value)
        clauses = [
            f"CAST({alias}.{quote_identifier(col)} AS VARCHAR) = {literal}"
            for alias, col in candidates
        ]
        return "WHERE " + " OR ".join(clauses)

    # ── string / type utilities ───────────────────────────────────────────

    def _question_overlap(self, question: str, label: str) -> int:
        tokens = [t for t in re.split(r"[^a-z0-9]+", label.lower()) if len(t) > 1]
        return sum(1 for t in tokens if t in question)

    def _compact(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    def _light_table_name(self, value: str) -> str:
        c = self._compact(value)
        for suffix in ("master", "mst", "table", "details", "detail"):
            c = c.replace(suffix, "")
        return c

    def _is_joinable(self, left_col: ColumnProfile, right_col: ColumnProfile) -> bool:
        l, r = left_col.dtype.upper(), right_col.dtype.upper()
        if l == r:
            return True
        if is_numeric_dtype(l) and is_numeric_dtype(r):
            return True
        if is_datetime_dtype(l) and is_datetime_dtype(r):
            return True
        if not is_numeric_dtype(l) and not is_datetime_dtype(l) and not is_numeric_dtype(r) and not is_datetime_dtype(r):
            return True
        return False

    def _is_key_or_audit_column(self, name: str) -> bool:
        c = self._compact(name)
        return c == "id" or c.endswith("id") or self._is_audit_column(name)

    def _is_audit_column(self, name: str) -> bool:
        return self._compact(name) in {
            "createdby", "createdon", "changedby", "changedon",
            "modifiedby", "modifiedon", "updatedby", "updatedon", "isactive",
        }

    def _has_any(self, text: str, terms: tuple[str, ...]) -> bool:
        for term in terms:
            if term != term.strip() or " " in term:
                if term in text:
                    return True
                continue
            if re.search(rf"\b{re.escape(term)}\b", text):
                return True
        return False