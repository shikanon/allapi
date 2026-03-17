from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_config


def _make_engine():
    cfg = get_config()
    connect_args = {}
    if cfg.database.url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if cfg.database.url.startswith("sqlite:///./"):
            sqlite_path = cfg.database.url[len("sqlite:///./") :]
            Path(sqlite_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    return create_engine(cfg.database.url, connect_args=connect_args, pool_pre_ping=True)


engine = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
