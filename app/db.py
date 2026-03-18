from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
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


def ensure_schema(engine) -> None:
    cfg = get_config()
    if not cfg.database.url.startswith("sqlite"):
        return

    with engine.begin() as conn:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}

        if "users" in tables:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(users)"))}
            if "balance_rmb" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN balance_rmb NUMERIC(20,6) NOT NULL DEFAULT 0"))
                if "balance_tokens" in cols:
                    conn.execute(
                        text(
                            "UPDATE users SET balance_rmb = balance_tokens WHERE balance_rmb = 0 AND balance_tokens IS NOT NULL"
                        )
                    )

        if "consumption_records" in tables:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(consumption_records)"))}
            if "amount_rmb" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE consumption_records ADD COLUMN amount_rmb NUMERIC(20,6) NOT NULL DEFAULT 0"
                    )
                )

        if "video_tasks" in tables:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(video_tasks)"))}
            if "charged_amount_rmb" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE video_tasks ADD COLUMN charged_amount_rmb NUMERIC(20,6) NULL"
                    )
                )


engine = _make_engine()
ensure_schema(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
