"""
DuckDB Connection Manager

Manages a single persistent in-memory DuckDB connection.
Thread-safe singleton pattern ensures consistent access
across the application lifecycle.
"""

import duckdb
import threading

_lock = threading.Lock()
_connection: duckdb.DuckDBPyConnection | None = None


def get_connection() -> duckdb.DuckDBPyConnection:
    """
    Get or create the singleton DuckDB in-memory connection.

    Returns:
        DuckDB connection instance.
    """
    global _connection
    with _lock:
        if _connection is None:
            _connection = duckdb.connect(database=":memory:")
            # Install and load extensions for broader format support
            _connection.execute("INSTALL httpfs; LOAD httpfs;")
        return _connection


def close_connection() -> None:
    """Close the DuckDB connection gracefully."""
    global _connection
    with _lock:
        if _connection is not None:
            try:
                _connection.close()
            except Exception:
                pass
            _connection = None


def health_check() -> dict:
    """
    Check DuckDB connection health.

    Returns:
        Dictionary with status and version info.
    """
    try:
        conn = get_connection()
        result = conn.execute("SELECT version()").fetchone()
        return {
            "status": "healthy",
            "version": result[0] if result else "unknown",
            "engine": "duckdb",
            "mode": "in-memory",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "engine": "duckdb",
        }
