from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_config
from app.models import ConsumptionRecord, User


def detect_video_input(payload: dict[str, Any]) -> bool:
    content = payload.get("content")
    if not isinstance(content, list):
        return False
    for item in content:
        if not isinstance(item, dict):
            continue
        t = item.get("type")
        role = item.get("role")
        if isinstance(t, str) and t == "video_url":
            return True
        if isinstance(role, str) and role == "reference_video":
            return True
    return False


def quote_rmb(*, total_tokens: int, has_video_input: bool) -> Decimal:
    cfg = get_config()
    price = (
        cfg.pricing.money.with_video_input_rmb_per_million
        if has_video_input
        else cfg.pricing.money.without_video_input_rmb_per_million
    )
    return (Decimal(str(total_tokens)) * Decimal(str(price))) / Decimal("1000000")


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def ensure_balance(db: Session, user: User, required_rmb: Decimal):
    db.refresh(user)
    if _as_decimal(user.balance_rmb) < required_rmb:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="余额不足")


def charge_and_record(
    db: Session,
    *,
    user: User,
    endpoint: str,
    tokens: Decimal,
    amount_rmb: Decimal,
    status_text: str,
    request_id: Optional[str],
    upstream_status_code: Optional[int],
    task_id: Optional[str] = None,
    error_message: Optional[str] = None,
):
    db.refresh(user)
    balance_before = _as_decimal(user.balance_rmb)
    if tokens < 0:
        tokens = Decimal("0")

    if amount_rmb < 0:
        amount_rmb = Decimal("0")

    if amount_rmb > 0 and balance_before < amount_rmb:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="余额不足")

    balance_after = balance_before - amount_rmb
    user.balance_rmb = balance_after

    record = ConsumptionRecord(
        user_id=user.id,
        endpoint=endpoint,
        task_id=task_id,
        request_id=request_id,
        tokens_charged=tokens,
        amount_rmb=amount_rmb,
        balance_before=balance_before,
        balance_after=balance_after,
        status=status_text,
        upstream_status_code=upstream_status_code,
        error_message=error_message,
    )
    db.add(record)
    db.add(user)
    db.commit()
    db.refresh(user)
    return record
