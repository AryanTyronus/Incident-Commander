from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter

from backend.app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check - confirms application is alive."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness_check() -> dict[str, Any]:
    """Readiness check - verifies essential dependencies."""
    checks = {}

    # Check SQLite
    try:
        conn = sqlite3.connect(settings.DATABASE_PATH, timeout=5)
        conn.execute("SELECT 1")
        conn.close()
        checks["sqlite"] = "ok"
    except Exception as e:
        checks["sqlite"] = f"error: {e}"

    # Check ChromaDB (optional)
    try:
        import chromadb
        client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIRECTORY)
        client.heartbeat()
        checks["chromadb"] = "ok"
    except Exception as e:
        checks["chromadb"] = f"warning: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }
