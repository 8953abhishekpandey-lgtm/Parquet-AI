from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import files, health, query
from backend.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title="Chat with Dynamic Parquet Files",
    description=(
        "Fully local AI-powered parquet analytics using FastAPI, DuckDB, "
        "Spark, sentence-transformers, and Qdrant."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(files.router)
app.include_router(query.router)


@app.on_event("startup")
def startup() -> None:
    settings.ensure_directories()

