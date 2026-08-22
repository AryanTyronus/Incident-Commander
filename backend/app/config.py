from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_config_file = Path(__file__).resolve()


def _find_repo_root() -> Path:
    """Return the repository root, located by walking up to a marker file.

    Anchoring on ``pyproject.toml`` keeps the result correct no matter how deep
    this module sits, instead of relying on a hard-coded ``parents[]`` index.
    Falls back to the packaged layout (``<root>/backend/app/config.py``) when
    the marker is absent, e.g. in a stripped-down deployment image.
    """
    for candidate in _config_file.parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return _config_file.parents[2]


_base_dir = _find_repo_root()

# Load .env from project root
load_dotenv(_base_dir / ".env")


def resolve_repo_path(value: str) -> str:
    """Resolve a configured path to an absolute one anchored at the repo root.

    Absolute values pass through untouched so deployments can point anywhere.
    Relative values (``.env`` ships ``DATABASE_PATH=data/incidents.db``) are
    anchored to the repository root rather than the current working directory,
    so ``uvicorn`` started from the repo root and from ``backend/`` open the
    exact same SQLite file.
    """
    path = Path(value)
    if not path.is_absolute():
        path = _base_dir / path
    return str(path)


class Settings:
    """Application configuration loaded from environment variables."""

    DATABASE_PATH: str = resolve_repo_path(os.getenv("DATABASE_PATH", "data/incidents.db"))
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Ollama configuration
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "60"))

    # Phase 3: Log analysis
    LOG_BURST_WINDOW_SECONDS: float = float(os.getenv("LOG_BURST_WINDOW_SECONDS", "60"))
    LOG_BURST_ERROR_THRESHOLD: int = int(os.getenv("LOG_BURST_ERROR_THRESHOLD", "10"))

    # Phase 3: Git forensics
    GIT_LOOKBACK_HOURS: float = float(os.getenv("GIT_LOOKBACK_HOURS", "24"))
    GIT_MAX_COMMITS: int = int(os.getenv("GIT_MAX_COMMITS", "50"))

    # Phase 3: RAG/Retrieval
    CHROMA_PERSIST_DIRECTORY: str = resolve_repo_path(
        os.getenv("CHROMA_PERSIST_DIRECTORY", "data/chroma")
    )
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))
    RUNBOOK_DIRECTORY: str = resolve_repo_path(os.getenv("RUNBOOK_DIRECTORY", "runbooks"))

    # Phase 4: RCA Confidence Weights
    RCA_SUPPORT_WEIGHT: float = float(os.getenv("RCA_SUPPORT_WEIGHT", "0.30"))
    RCA_TEMPORAL_WEIGHT: float = float(os.getenv("RCA_TEMPORAL_WEIGHT", "0.20"))
    RCA_CORRELATION_WEIGHT: float = float(os.getenv("RCA_CORRELATION_WEIGHT", "0.20"))
    RCA_DOCUMENTATION_WEIGHT: float = float(os.getenv("RCA_DOCUMENTATION_WEIGHT", "0.10"))
    RCA_CONTRADICTION_PENALTY: float = float(os.getenv("RCA_CONTRADICTION_PENALTY", "0.15"))
    RCA_MISSING_DATA_PENALTY: float = float(os.getenv("RCA_MISSING_DATA_PENALTY", "0.10"))


settings = Settings()
