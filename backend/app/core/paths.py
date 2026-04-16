from __future__ import annotations

import os
import sys
from pathlib import Path


APP_DIR_NAME = "ResearchFlow"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def bundle_root() -> Path:
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return repo_root()


def default_data_dir() -> Path:
    configured = os.getenv("DR_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()

    if is_frozen():
        local_appdata = os.getenv("LOCALAPPDATA", "").strip()
        if local_appdata:
            return Path(local_appdata) / APP_DIR_NAME
        return Path.home() / f".{APP_DIR_NAME.lower()}"

    return repo_root() / "backend" / ".data"


def default_reports_dir() -> Path:
    configured = os.getenv("DR_REPORTS_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    return default_data_dir() / "reports"


def default_frontend_dist_dir() -> Path:
    configured = os.getenv("DR_FRONTEND_DIST_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()

    if is_frozen():
        return bundle_root() / "frontend_dist"

    return repo_root() / "frontend" / "dist"
