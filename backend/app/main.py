from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import incidents as incidents_api
from backend.app.api import webhooks as webhooks_api
from backend.app.api.demo import router as demo_router
from backend.app.api.health import router as health_router
from backend.app.api.stream import router as stream_router
from backend.app.config import settings
from backend.app.db import get_connection, initialize_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    conn = get_connection(settings.DATABASE_PATH)
    initialize_database(conn)
    conn.close()
    yield


app = FastAPI(
    title="Incident Commander",
    description="Incident management with agent orchestration",
    version="0.5.0",
    lifespan=lifespan,
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents_api.router)
app.include_router(incidents_api.remediation_router)
app.include_router(webhooks_api.router)
app.include_router(health_router)
app.include_router(stream_router)
app.include_router(demo_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
