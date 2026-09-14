from __future__ import annotations

import os
import shutil
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from apix.common.config import data_dir, settings


class Base(DeclarativeBase):
    pass


_ENGINE = None
_SESSION = None


def _sqlite_path() -> Path:
    bundled = data_dir() / "apix.db"
    if not os.environ.get("VERCEL"):
        return bundled
    dest = Path("/tmp/apix.db")
    if bundled.exists() and (not dest.exists() or dest.stat().st_size != bundled.stat().st_size):
        shutil.copy2(bundled, dest)
    return dest if dest.exists() else bundled


def database_url() -> str:
    url = str(settings().get("database_url") or "sqlite:///./data/apix.db")
    if url.startswith("sqlite:///"):
        path = _sqlite_path()
        return f"sqlite:///{path.as_posix()}"
    return url


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        url = database_url()
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _ENGINE = create_engine(url, future=True, connect_args=connect_args)
    return _ENGINE


def session_factory() -> sessionmaker[Session]:
    global _SESSION
    if _SESSION is None:
        _SESSION = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SESSION


def get_session() -> Session:
    return session_factory()()
