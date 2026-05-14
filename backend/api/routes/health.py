from fastapi import APIRouter

from backend.core.config import get_settings
from backend.qdrant.vector_store import QdrantVectorStore


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()

    # Check Qdrant connection
    qdrant_ok = False
    try:
        store = QdrantVectorStore()
        qdrant_ok = store.is_connected()
    except Exception:
        pass

    # DuckDB is always available (in-memory)
    duckdb_ok = True
    try:
        import duckdb
        conn = duckdb.connect(":memory:")
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception:
        duckdb_ok = False

    # Claude availability
    claude_available = bool(settings.anthropic_api_key and settings.enable_claude_reasoning)

    return {
        "status": "ok" if (qdrant_ok and duckdb_ok) else "degraded",
        "app": settings.app_name,
        "embedding_model": settings.embedding_model,
        "qdrant_mode": settings.qdrant_mode,
        "qdrant_url": settings.qdrant_url,
        "services": {
            "qdrant": qdrant_ok,
            "duckdb": duckdb_ok,
            "claude": claude_available,
        },
    }
