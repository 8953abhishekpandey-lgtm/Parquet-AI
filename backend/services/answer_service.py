"""
Answer Service — Wrapper for natural language answer generation.

Provides a clean interface for generating answers from query results.
"""

from backend.anthropic_client.answer_generator import generate_answer


async def generate_nl_answer(
    question: str,
    results: list[dict],
    columns: list[str],
) -> tuple[str, int]:
    """
    Generate a natural language answer from query results.

    Args:
        question: The user's original question.
        results: Query result rows.
        columns: Column names.

    Returns:
        Tuple of (answer_text, tokens_used).
    """
    return generate_answer(question, results, columns)
