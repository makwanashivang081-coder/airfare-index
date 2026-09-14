"""Vercel FastAPI entrypoint. Local use: python scripts/run_api.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from apix.api.main import app

__all__ = ["app"]
