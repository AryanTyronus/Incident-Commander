from __future__ import annotations

import os
from pathlib import Path

_base_dir = Path(__file__).resolve().parent.parent.parent


class Settings:
    """Application configuration loaded from environment variables."""

    DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(_base_dir / "data" / "incidents.db"))
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Ollama configuration
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "60"))

    # Phase 3: Log analysis
    LOG_BURST_WINDOW_SECONDS: float = float(os.getenv("LOG_BURST_WINDOW_SECONDS", "60"))
    LOG_BURST_ERROR_THRESHOLD: int = int(os.getenv("LOG_BURST_ERROR_THRESHOLD", "10"))

    # Phase 3: Git forensics
    GIT_LOOKBACK_HOURS: float = float(os.getenv("GIT_LOOKBACK_HOURS", "24"))
    GIT_MAX_COMMITS: int = int(os.getenv("GIT_MAX_COMMITS", "50"))

    # Phase 3: RAG/Retrieval
    CHROMA_PERSIST_DIRECTORY: str = os.getenv(
        "CHROMA_PERSIST_DIRECTORY", str(_base_dir / "data" / "chroma")
    )
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))
    RUNBOOK_DIRECTORY: str = os.getenv("RUNBOOK_DIRECTORY", str(_base_dir / "runbooks"))

    # Phase 4: RCA Confidence Weights
    RCA_SUPPORT_WEIGHT: float = float(os.getenv("RCA_SUPPORT_WEIGHT", "0.30"))
    RCA_TEMPORAL_WEIGHT: float = float(os.getenv("RCA_TEMPORAL_WEIGHT", "0.20"))
    RCA_CORRELATION_WEIGHT: float = float(os.getenv("RCA_CORRELATION_WEIGHT", "0.20"))
    RCA_DOCUMENTATION_WEIGHT: float = float(os.getenv("RCA_DOCUMENTATION_WEIGHT", "0.10"))
    RCA_CONTRADICTION_PENALTY: float = float(os.getenv("RCA_CONTRADICTION_PENALTY", "0.15"))
    RCA_MISSING_DATA_PENALTY: float = float(os.getenv("RCA_MISSING_DATA_PENALTY", "0.10"))


settings = Settings()
