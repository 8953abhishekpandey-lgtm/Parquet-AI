from __future__ import annotations

from typing import Any

from backend.models import GeneratedSQL


class TemplateResponseBuilder:
    def build(self, plan: GeneratedSQL, rows: list[dict[str, Any]]) -> str:
        if not rows:
            if plan.intent in {"outlier_detection", "multi_outlier_detection"}:
                return "No abnormal rows crossed the z-score threshold in the returned result set."
            return "No rows were returned for this question."

        first = rows[0]
        metric_label = self._label(plan.metric_column or "records")

        if plan.intent == "multi_dataset_counts":
            return f"Returned row counts for {len(rows)} uploaded parquet datasets."

        if plan.intent in {"multi_dataset_preview", "multi_dataset_join_preview"}:
            return f"Returned {len(rows)} rows from the best matching uploaded dataset flow."

        if plan.intent.startswith("multi_") and plan.group_by_columns:
            group = plan.group_by_columns[0]
            if "metric_value" in first:
                return (
                    f"Returned {len(rows)} rows across uploaded datasets. "
                    f"The leading {group} value is {first.get(group)} with {self._format_value(first.get('metric_value'))}."
                )
            return f"Returned {len(rows)} rows across uploaded datasets."

        if plan.intent.startswith("highest") and plan.group_by_columns:
            group = plan.group_by_columns[0]
            return (
                f"{first.get(group)} has the highest {metric_label} "
                f"with a value of {self._format_value(first.get('metric_value'))}."
            )

        if plan.intent.startswith("lowest") and plan.group_by_columns:
            group = plan.group_by_columns[0]
            return (
                f"{first.get(group)} has the lowest {metric_label} "
                f"with a value of {self._format_value(first.get('metric_value'))}."
            )

        if plan.intent in {"average", "total", "highest", "lowest"}:
            return f"The {plan.intent} {metric_label} is {self._format_value(first.get('metric_value'))}."

        if plan.intent.endswith("_by_dimension") and plan.group_by_columns:
            group = plan.group_by_columns[0]
            return (
                f"Returned {len(rows)} grouped result rows by {group}. "
                f"The leading value is {first.get(group)} with {self._format_value(first.get('metric_value'))}."
            )

        if "trend" in plan.intent:
            return f"Returned {len(rows)} trend rows for {metric_label}."

        if plan.intent == "outlier_detection":
            return f"Found {len(rows)} potential abnormal rows using z-score analysis on {metric_label}."

        if plan.intent.startswith("count"):
            if "record_count" in first and not plan.group_by_columns:
                return f"The uploaded parquet contains {self._format_value(first.get('record_count'))} records."
            return f"Returned {len(rows)} count rows."

        return f"Returned {len(rows)} rows for the question."

    def _format_value(self, value: Any) -> str:
        if isinstance(value, float):
            return f"{value:,.4g}"
        if isinstance(value, int):
            return f"{value:,}"
        return str(value)

    def _label(self, value: str) -> str:
        return value.replace("_", " ").strip()
