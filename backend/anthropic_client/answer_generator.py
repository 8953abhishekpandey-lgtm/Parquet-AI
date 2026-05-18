"""
Answer Generator — Natural language answers from query results.

Takes SQL execution results (max 20 rows) and generates
a friendly, data-driven answer. Only result rows and the
original question are sent to Claude — never raw parquet data.
"""

import json
import os

from backend.anthropic_client.client import call_claude, PRIMARY_ANSWER_MODEL

MAX_ANSWER_ROWS = int(os.getenv("MAX_ANSWER_ROWS", "20"))

ANSWER_SYSTEM_PROMPT = """You are a friendly data analyst assistant.
Rules:
1. Answer in 2-4 sentences maximum
2. Bold the most important numbers or names using **value**
3. If multiple values, use a clean bullet list
4. End with one insight or trend observation
5. Be specific — mention actual numbers from the data
6. If data is empty, say "No data found matching your criteria"
7. Do not say "all rows" unless the result contains an explicit total/count proving it.
8. If a field value is "NULL" or "Unknown / Not populated", clearly say the source field is not populated instead of treating it as a real category.
9. For grouped report results, summarize each row as a compact table-like bullet with the key dimensions and counts.
"""


def generate_answer(
    user_question: str,
    results: list[dict],
    columns: list[str],
) -> tuple[str, int]:
    """
    Generate a natural language answer from SQL results.

    Args:
        user_question: The original user question.
        results: Query results (list of dicts), will be capped at MAX_ANSWER_ROWS.
        columns: Column names from the result set.

    Returns:
        Tuple of (natural_language_answer, tokens_used).
    """
    # Cap results sent to Claude
    truncated_results = results[:MAX_ANSWER_ROWS]

    # Build concise JSON representation
    results_json = json.dumps(truncated_results, default=str, indent=None)

    user_prompt = f"""Question: {user_question}

Columns: {', '.join(columns)}
Results ({len(truncated_results)} of {len(results)} rows):
{results_json}

Provide a clear, direct answer."""

    answer, tokens = call_claude(
        system_prompt=ANSWER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=PRIMARY_ANSWER_MODEL,
        max_tokens=400,
        temperature=0.3,
    )

    return answer, tokens
