from __future__ import annotations

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.models import ApiKeyMapping, Base, ModelMapping, User


def main():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        token = secrets.token_hex(16)
        user = User(token=token, balance_tokens=1_000_000)
        db.add(user)

        if not db.query(ModelMapping).filter(ModelMapping.public_name == "next-light").one_or_none():
            db.add(
                ModelMapping(public_name="next-light", upstream_model="doubao-seedance-2-0-260128")
            )

        db.commit()
        print(token)
    finally:
        db.close()


if __name__ == "__main__":
    main()
