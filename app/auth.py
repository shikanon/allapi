from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_config
from app.db import get_db
from app.models import User


def _extract_token(authorization: Optional[str], x_user_token: Optional[str]) -> Optional[str]:
    if x_user_token:
        return x_user_token.strip() or None
    if not authorization:
        return None
    cfg = get_config()
    prefix = (cfg.auth.bearer_prefix or "Bearer").strip()
    value = authorization.strip()
    if value.lower().startswith(prefix.lower() + " "):
        return value[len(prefix) + 1 :].strip() or None
    return value or None


def get_current_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_user_token: Optional[str] = Header(default=None, alias="X-User-Token"),
):
    token = _extract_token(authorization, x_user_token)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少用户Token")

    user = db.query(User).filter(User.token == token).one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户Token无效")
    return user
