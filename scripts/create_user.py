from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.models import Base, User


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--balance_rmb", type=float, default=None, help="初始余额（人民币）")
    parser.add_argument("--balance", type=float, default=None, help="初始余额（人民币，兼容旧参数名）")
    parser.add_argument("--token", type=str, default="", help="指定用户Token，不填则随机生成")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        token = (args.token or "").strip() or secrets.token_hex(16)
        balance_rmb = args.balance_rmb
        if balance_rmb is None:
            balance_rmb = args.balance
        if balance_rmb is None:
            balance_rmb = 0
        user = User(token=token, balance_rmb=float(balance_rmb))
        db.add(user)
        db.commit()
        print(token)
    finally:
        db.close()


if __name__ == "__main__":
    main()
