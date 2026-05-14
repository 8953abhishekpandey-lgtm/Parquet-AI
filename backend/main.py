"""
Parquet AI — FastAPI Application Entry Point

Text-to-SQL analytics platform with local DuckDB execution.
Parquet data never leaves the local system. Only schema metadata
and limited result rows are sent to Claude API for SQL generation
and natural language answers.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from backend.api.routes import upload, query, query_stream, schema, files, results, health
from backend.duckdb.connection import get_connection, close_connection
from backend.metadata.schema_store import SchemaStore
from backend.metadata.file_registry import FileRegistry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    os.makedirs(os.getenv("UPLOAD_DIR", "./uploads"), exist_ok=True)
    os.makedirs(os.getenv("METADATA_DIR", "./metadata"), exist_ok=True)
    os.makedirs(os.path.join(os.getenv("METADATA_DIR", "./metadata"), "schemas"), exist_ok=True)

    # Initialize stores
    app.state.schema_store = SchemaStore(os.getenv("METADATA_DIR", "./metadata"))
    app.state.file_registry = FileRegistry(os.getenv("METADATA_DIR", "./metadata"))

    # Initialize DuckDB
    conn = get_connection()
    print(f"✅ DuckDB initialized (in-memory)")
    print(f"📂 Upload dir: {os.getenv('UPLOAD_DIR', './uploads')}")
    print(f"📋 Metadata dir: {os.getenv('METADATA_DIR', './metadata')}")
    print(f"🤖 Primary model: {os.getenv('PRIMARY_MODEL', 'claude-haiku-20240307')}")

    yield

    # Shutdown
    close_connection()
    print("🛑 DuckDB connection closed")


app = FastAPI(
    title="Parquet AI — Text-to-SQL Analytics",
    description="Enterprise-grade AI analytics platform with local DuckDB execution",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(query.router, prefix="/api", tags=["Query"])
app.include_router(query_stream.router, prefix="/api", tags=["Query Stream"])
app.include_router(schema.router, prefix="/api", tags=["Schema"])
app.include_router(files.router, prefix="/api", tags=["Files"])
app.include_router(results.router, prefix="/api", tags=["Results"])
