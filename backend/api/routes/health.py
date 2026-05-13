from fastapi import APIRouter

from backend.core.config import get_settings


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "embedding_model": settings.embedding_model,
        "qdrant_mode": settings.qdrant_mode,
        "qdrant_url": settings.qdrant_url,
    }
