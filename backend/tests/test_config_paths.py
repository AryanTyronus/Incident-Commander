"""Regression tests for deterministic configuration path resolution.

Launching Uvicorn from the repository root and from ``backend/`` used to open two
different SQLite files, because ``DATABASE_PATH`` was resolved relative to the
current working directory.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from backend.app.config import _find_repo_root, resolve_repo_path, settings

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_repo_root_is_located_by_marker_file() -> None:
    root = _find_repo_root()
    assert root == REPO_ROOT
    assert (root / "pyproject.toml").is_file()


def test_default_database_path_is_absolute() -> None:
    assert Path(settings.DATABASE_PATH).is_absolute()


def test_default_database_path_points_at_repo_level_data_dir() -> None:
    assert Path(settings.DATABASE_PATH) == REPO_ROOT / "data" / "incidents.db"


def test_other_configured_paths_are_absolute() -> None:
    assert Path(settings.CHROMA_PERSIST_DIRECTORY).is_absolute()
    assert Path(settings.RUNBOOK_DIRECTORY).is_absolute()


def test_relative_values_anchor_to_repo_root_not_cwd() -> None:
    assert resolve_repo_path("data/incidents.db") == str(REPO_ROOT / "data" / "incidents.db")


def test_absolute_values_pass_through_unchanged() -> None:
    absolute = str(Path("/tmp") / "elsewhere" / "incidents.db")
    assert resolve_repo_path(absolute) == absolute


def _database_path_from_cwd(cwd: Path) -> str:
    """Import the settings in a fresh interpreter started from ``cwd``."""
    program = "from backend.app.config import settings; print(settings.DATABASE_PATH)"
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_database_path_is_identical_from_repo_root_and_backend() -> None:
    """The bug this guards: one database, whichever directory serves the app."""
    from_root = _database_path_from_cwd(REPO_ROOT)
    from_backend = _database_path_from_cwd(REPO_ROOT / "backend")

    assert from_root == from_backend
    assert from_root == str(REPO_ROOT / "data" / "incidents.db")


def test_no_duplicate_database_below_backend() -> None:
    assert not (REPO_ROOT / "backend" / "data" / "incidents.db").exists()
