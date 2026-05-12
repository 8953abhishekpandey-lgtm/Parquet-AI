from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Chat with Dynamic Parquet Files"
    project_root: Path = Path(__file__).resolve().parents[2]
    upload_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "uploads")
    dataset_store_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1] / "storage" / "datasets"
    )

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "parquet_semantic_metadata"
    qdrant_mode: str = "embedded"
    qdrant_local_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1] / "storage" / "qdrant"
    )
    # default embedding model (keep small to match existing stored vectors)
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 32
    vector_size: int = 384

    sample_rows: int = 20
    profile_top_values: int = 8
    query_row_limit: int = 100
    semantic_top_k: int = 12
    enable_spark_schema: bool = True

    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def ensure_directories(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_store_dir.mkdir(parents=True, exist_ok=True)
        self.qdrant_local_path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
