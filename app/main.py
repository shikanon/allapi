from __future__ import annotations

import json
import logging
import os
import asyncio
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from app.auth import get_current_user
from app.billing import (
    charge_and_record,
    detect_video_input,
    ensure_balance,
    quote_rmb,
)
from datetime import datetime
from app.config import get_config
from app.db import engine, get_db
from app.models import ApiKeyMapping, Base, ModelMapping, User
from app.models import ConsumptionRecord
from app.models import VideoTask
from app.proxy import forward_json


def _setup_logging():
    Path("logs").mkdir(parents=True, exist_ok=True)
    cfg = get_config()
    
    # 优先使用环境变量，其次使用配置文件
    level_name = (os.getenv("LOG_LEVEL") or cfg.app.log_level or "INFO").upper().strip()
    level = getattr(logging, level_name, logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler("logs/app.log")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    app_logger = logging.getLogger("allapi")
    app_logger.handlers = []
    app_logger.addHandler(file_handler)
    app_logger.addHandler(stream_handler)
    app_logger.setLevel(level)
    app_logger.propagate = False

    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.INFO)


_setup_logging()
logger = logging.getLogger("allapi")

app = FastAPI(title="API中转售卖系统", version="0.1.0")


@app.on_event("startup")
def _startup():
    Path("data").mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    body_bytes = await request.body()
    scope = dict(request.scope)
    scope.setdefault("state", {})
    scope["state"] = dict(scope["state"])
    scope["state"]["request_id"] = request_id
    scope["state"]["raw_body"] = body_bytes

    consumed = False

    async def receive():
        nonlocal consumed
        if consumed:
            return {"type": "http.request", "body": b"", "more_body": False}
        consumed = True
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    req = Request(scope, receive)

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "incoming %s %s headers=%s query=%s body=%s",
            req.method,
            req.url.path,
            _redact_headers(req.headers),
            dict(req.query_params),
            _body_preview(body_bytes, req.headers),
        )

    response = await call_next(req)
    response.headers["X-Request-Id"] = request_id

    if logger.isEnabledFor(logging.DEBUG):
        # We can't easily read the response body in middleware without consuming it,
        # but we can log status and headers.
        logger.debug(
            "outgoing %s %s status=%s headers=%s",
            req.method,
            req.url.path,
            response.status_code,
            _redact_headers(response.headers),
        )
    return response


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or uuid.uuid4().hex


def _allow_sensitive_logs() -> bool:
    v = (os.getenv("LOG_INCLUDE_SENSITIVE") or "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _redact_token(value: str) -> str:
    if _allow_sensitive_logs():
        return (value or "").strip()
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= 10:
        return "***"
    return v[:4] + "..." + v[-4:]


def _redact_headers(headers: Headers) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in {"authorization", "x-user-token"}:
            out[k] = _redact_token(v)
        else:
            out[k] = v
    return out


def _body_preview(body_bytes: bytes, headers: Headers) -> Any:
    max_chars_env = os.getenv("LOG_BODY_MAX_CHARS")
    max_chars = 20000
    if max_chars_env is not None and max_chars_env.strip() != "":
        try:
            max_chars = int(max_chars_env)
        except Exception:
            max_chars = 20000

    content_type = headers.get("content-type") or ""
    if "application/json" in content_type.lower():
        try:
            obj = json.loads(body_bytes.decode("utf-8")) if body_bytes else None
            return obj if _allow_sensitive_logs() else _redact_body_obj(obj)
        except Exception:
            pass
    if not body_bytes:
        return ""
    text = None
    try:
        text = body_bytes.decode("utf-8", errors="replace")
    except Exception:
        text = repr(body_bytes)
    if max_chars <= 0:
        return text
    return text[:max_chars]


def _redact_body_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            lk = k.lower() if isinstance(k, str) else ""
            if lk in {"authorization", "token", "access_token", "api_key"} and isinstance(v, str):
                out[k] = _redact_token(v)
            else:
                out[k] = _redact_body_obj(v)
        return out
    if isinstance(obj, list):
        return [_redact_body_obj(x) for x in obj]
    return obj


def _resolve_upstream_model(db: Session, public_model: str) -> str:
    mapping = db.query(ModelMapping).filter(ModelMapping.public_name == public_model).one_or_none()
    if mapping:
        return mapping.upstream_model
    cfg = get_config()
    return cfg.upstream.model_mapping.get(public_model, public_model)


def _resolve_upstream_bearer(db: Session, public_api_key: Optional[str]) -> str:
    cfg = get_config()
    if public_api_key:
        mapping = (
            db.query(ApiKeyMapping)
            .filter(ApiKeyMapping.public_key == public_api_key)
            .one_or_none()
        )
        if mapping:
            return mapping.upstream_bearer_token
        if public_api_key in cfg.upstream.api_key_mapping:
            return cfg.upstream.api_key_mapping[public_api_key]
    return cfg.upstream.default_bearer_token


def _build_upstream_headers(bearer_token: str) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    return headers


def _redact_upstream_headers(headers: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() == "authorization":
            out[k] = _redact_token(v)
        else:
            out[k] = v
    return out


def _safe_json(resp_content: bytes) -> Any:
    try:
        return json.loads(resp_content.decode("utf-8"))
    except Exception:
        return None


@app.post("/v1/video/tasks")
async def create_video_task(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    request_id = _get_request_id(request)
    raw_body = getattr(request.state, "raw_body", None)
    payload = _safe_json(raw_body) if isinstance(raw_body, (bytes, bytearray)) else await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求体必须是JSON对象")

    public_model = payload.get("model")
    if not isinstance(public_model, str) or not public_model.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少model参数")

    payload = dict(payload)
    public_api_key = payload.pop("api_key", None)
    upstream_model = _resolve_upstream_model(db, public_model.strip())
    payload["model"] = upstream_model
    bearer = _resolve_upstream_bearer(db, public_api_key if isinstance(public_api_key, str) else None)

    upstream_headers = _build_upstream_headers(bearer)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "mapping request_id=%s model=%s->%s api_key_present=%s",
            request_id,
            public_model.strip(),
            upstream_model,
            bool(public_api_key),
        )
        logger.debug(
            "forward request_id=%s method=POST path=%s headers=%s body=%s",
            request_id,
            "/api/v3/contents/generations/tasks",
            _redact_upstream_headers(upstream_headers),
            payload,
        )

    has_video_input = detect_video_input(payload)

    try:
        resp = await forward_json(
            method="POST",
            path="/api/v3/contents/generations/tasks",
            headers=upstream_headers,
            json_body=payload,
        )
    except Exception as e:
        logger.exception("upstream request failed", extra={"request_id": request_id})
        charge_and_record(
            db,
            user=user,
            endpoint="video.create",
            tokens=Decimal("0"),
            amount_rmb=Decimal("0"),
            status_text="upstream_error",
            request_id=request_id,
            upstream_status_code=None,
            error_message=str(e),
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="上游请求失败")

    body = _safe_json(resp.content)
    task_id = None
    if isinstance(body, dict) and isinstance(body.get("id"), str):
        task_id = body.get("id")

    if 200 <= resp.status_code < 300:
        charge_and_record(
            db,
            user=user,
            endpoint="video.create",
            tokens=Decimal("0"),
            amount_rmb=Decimal("0"),
            status_text="success",
            request_id=request_id,
            upstream_status_code=resp.status_code,
            task_id=task_id,
        )

        if task_id:
            existing = (
                db.query(VideoTask)
                .filter(VideoTask.user_id == user.id, VideoTask.task_id == task_id)
                .one_or_none()
            )
            if not existing:
                vt = VideoTask(
                    user_id=user.id,
                    task_id=task_id,
                    public_model=public_model.strip(),
                    upstream_model=upstream_model,
                    has_video_input=bool(has_video_input),
                )
                db.add(vt)
                db.commit()
    else:
        charge_and_record(
            db,
            user=user,
            endpoint="video.create",
            tokens=Decimal("0"),
            amount_rmb=Decimal("0"),
            status_text="failed",
            request_id=request_id,
            upstream_status_code=resp.status_code,
            task_id=task_id,
            error_message=str(body)[:2000] if body is not None else resp.text[:2000],
        )

    return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type"))


@app.websocket("/v1/video/tasks/ws")
async def generate_video_task_ws(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    await websocket.accept()
    request_id = uuid.uuid4().hex
    
    try:
        # 1. 接收认证和参数
        # 客户端应首先发送一个 JSON，包含 token 和任务参数
        initial_data = await websocket.receive_json()
        if not isinstance(initial_data, dict):
            await websocket.send_json({"type": "error", "message": "Invalid initial data format"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        token = initial_data.get("token")
        if not token:
            # 尝试从 query params 获取
            token = websocket.query_params.get("token")
        
        if not token:
            await websocket.send_json({"type": "error", "message": "Missing authentication token"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        user = db.query(User).filter(User.token == token).one_or_none()
        if not user or not user.is_active:
            await websocket.send_json({"type": "error", "message": "Invalid authentication token"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        payload = initial_data.get("payload")
        if not isinstance(payload, dict):
            await websocket.send_json({"type": "error", "message": "Missing or invalid payload"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # 2. 准备任务参数
        poll_interval_seconds = payload.pop("poll_interval_seconds", 2)
        timeout_seconds = payload.pop("timeout_seconds", 300)
        try:
            poll_interval_seconds = float(poll_interval_seconds)
        except Exception:
            poll_interval_seconds = 2
        try:
            timeout_seconds = float(timeout_seconds)
        except Exception:
            timeout_seconds = 300
        poll_interval_seconds = max(0.2, min(poll_interval_seconds, 10.0))
        timeout_seconds = max(1.0, min(timeout_seconds, 1800.0))

        public_model = payload.get("model")
        if not isinstance(public_model, str) or not public_model.strip():
            await websocket.send_json({"type": "error", "message": "Missing model parameter"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        payload = dict(payload)
        public_api_key = payload.pop("api_key", None)
        upstream_model = _resolve_upstream_model(db, public_model.strip())
        payload["model"] = upstream_model
        bearer = _resolve_upstream_bearer(db, public_api_key if isinstance(public_api_key, str) else None)
        upstream_headers = _build_upstream_headers(bearer)
        has_video_input = detect_video_input(payload)

        # 3. 创建任务
        await websocket.send_json({"type": "status", "status": "creating", "message": "正在创建视频生成任务..."})
        
        try:
            create_resp = await forward_json(
                method="POST",
                path="/api/v3/contents/generations/tasks",
                headers=upstream_headers,
                json_body=payload,
            )
        except Exception as e:
            logger.exception("upstream request failed", extra={"request_id": request_id})
            charge_and_record(
                db,
                user=user,
                endpoint="video.generate_ws",
                tokens=Decimal("0"),
                amount_rmb=Decimal("0"),
                status_text="upstream_error",
                request_id=request_id,
                upstream_status_code=None,
                error_message=str(e),
            )
            await websocket.send_json({"type": "error", "message": "上游请求失败"})
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return

        create_body = _safe_json(create_resp.content)
        if not (200 <= create_resp.status_code < 300):
            charge_and_record(
                db,
                user=user,
                endpoint="video.generate_ws",
                tokens=Decimal("0"),
                amount_rmb=Decimal("0"),
                status_text="failed",
                request_id=request_id,
                upstream_status_code=create_resp.status_code,
                error_message=str(create_body)[:2000] if create_body is not None else create_resp.text[:2000],
            )
            await websocket.send_json({"type": "error", "message": "任务创建失败", "detail": create_body})
            await websocket.close()
            return

        task_id = None
        if isinstance(create_body, dict) and isinstance(create_body.get("id"), str):
            task_id = create_body.get("id")
        
        if not task_id:
            await websocket.send_json({"type": "error", "message": "未获取到任务ID"})
            await websocket.close()
            return

        # 记录任务
        vt = db.query(VideoTask).filter(VideoTask.user_id == user.id, VideoTask.task_id == task_id).one_or_none()
        if not vt:
            vt = VideoTask(
                user_id=user.id,
                task_id=task_id,
                public_model=public_model.strip(),
                upstream_model=upstream_model,
                has_video_input=bool(has_video_input),
            )
            db.add(vt)
            db.commit()
            db.refresh(vt)

        await websocket.send_json({"type": "status", "status": "created", "task_id": task_id, "message": "任务创建成功，正在等待产出..."})

        # 4. 轮询逻辑
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        last_status = None

        while True:
            try:
                resp = await forward_json(
                    method="GET",
                    path=f"/api/v3/contents/generations/tasks/{task_id}",
                    headers=upstream_headers,
                    params={},
                )
            except Exception as e:
                logger.exception("upstream request failed", extra={"request_id": request_id})
                await websocket.send_json({"type": "status", "status": "upstream_error", "message": "查询上游失败，重试中..."})
                await asyncio.sleep(poll_interval_seconds)
                continue

            body = _safe_json(resp.content)
            if 200 <= resp.status_code < 300 and isinstance(body, dict):
                status_value = body.get("status")
                if isinstance(status_value, str):
                    st = status_value.lower()
                    if st != last_status:
                        last_status = st
                        await websocket.send_json({"type": "status", "status": st, "message": f"任务状态更新: {st}"})

                    if st == "succeeded":
                        # 扣费逻辑
                        content = body.get("content")
                        usage = body.get("usage")
                        video_url = None
                        if isinstance(content, dict) and isinstance(content.get("video_url"), str):
                            video_url = content.get("video_url")
                        total_tokens = None
                        if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
                            total_tokens = usage.get("total_tokens")

                        if bool(video_url) and isinstance(total_tokens, int) and total_tokens > 0:
                            if not vt.charged:
                                tokens_dec = Decimal(str(int(total_tokens)))
                                hv = bool(vt.has_video_input)
                                amount = quote_rmb(total_tokens=int(total_tokens), has_video_input=hv)
                                ensure_balance(db, user, Decimal(str(amount)))
                                charge_and_record(
                                    db,
                                    user=user,
                                    endpoint="video.charge",
                                    tokens=tokens_dec,
                                    amount_rmb=Decimal(str(amount)),
                                    status_text="success",
                                    request_id=request_id,
                                    upstream_status_code=resp.status_code,
                                    task_id=task_id,
                                )
                                vt.charged = True
                                vt.charged_tokens = int(total_tokens)
                                vt.charged_amount_rmb = float(amount)
                                vt.charged_at = datetime.utcnow()
                                db.add(vt)
                                db.commit()

                        charge_and_record(
                            db,
                            user=user,
                            endpoint="video.generate_ws",
                            tokens=Decimal("0"),
                            amount_rmb=Decimal("0"),
                            status_text="success",
                            request_id=request_id,
                            upstream_status_code=resp.status_code,
                            task_id=task_id,
                        )
                        await websocket.send_json({"type": "result", "data": body})
                        await websocket.close()
                        return

                    if st in {"failed", "cancelled", "expired"}:
                        charge_and_record(
                            db,
                            user=user,
                            endpoint="video.generate_ws",
                            tokens=Decimal("0"),
                            amount_rmb=Decimal("0"),
                            status_text=st,
                            request_id=request_id,
                            upstream_status_code=resp.status_code,
                            task_id=task_id,
                            error_message=str(body)[:2000],
                        )
                        await websocket.send_json({"type": "error", "message": f"任务执行终止: {st}", "detail": body})
                        await websocket.close()
                        return

            if loop.time() >= deadline:
                charge_and_record(
                    db,
                    user=user,
                    endpoint="video.generate_ws",
                    tokens=Decimal("0"),
                    amount_rmb=Decimal("0"),
                    status_text="timeout",
                    request_id=request_id,
                    upstream_status_code=resp.status_code if 'resp' in locals() else None,
                    task_id=task_id,
                )
                await websocket.send_json({"type": "error", "message": "等待任务结果超时"})
                await websocket.close()
                return

            await asyncio.sleep(poll_interval_seconds)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", extra={"request_id": request_id})
    except Exception as e:
        logger.exception("WebSocket error", extra={"request_id": request_id})
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
        except:
            pass

@app.post("/v1/video/tasks:generate")
async def generate_video_task(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    request_id = _get_request_id(request)
    raw_body = getattr(request.state, "raw_body", None)
    payload = _safe_json(raw_body) if isinstance(raw_body, (bytes, bytearray)) else await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求体必须是JSON对象")

    poll_interval_seconds = payload.pop("poll_interval_seconds", 2)
    timeout_seconds = payload.pop("timeout_seconds", 300)
    try:
        poll_interval_seconds = float(poll_interval_seconds)
    except Exception:
        poll_interval_seconds = 2
    try:
        timeout_seconds = float(timeout_seconds)
    except Exception:
        timeout_seconds = 300
    poll_interval_seconds = max(0.2, min(poll_interval_seconds, 10.0))
    timeout_seconds = max(1.0, min(timeout_seconds, 1800.0))

    public_model = payload.get("model")
    if not isinstance(public_model, str) or not public_model.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少model参数")

    payload = dict(payload)
    public_api_key = payload.pop("api_key", None)
    upstream_model = _resolve_upstream_model(db, public_model.strip())
    payload["model"] = upstream_model
    bearer = _resolve_upstream_bearer(db, public_api_key if isinstance(public_api_key, str) else None)
    upstream_headers = _build_upstream_headers(bearer)
    has_video_input = detect_video_input(payload)

    try:
        create_resp = await forward_json(
            method="POST",
            path="/api/v3/contents/generations/tasks",
            headers=upstream_headers,
            json_body=payload,
        )
    except Exception as e:
        logger.exception("upstream request failed", extra={"request_id": request_id})
        charge_and_record(
            db,
            user=user,
            endpoint="video.generate",
            tokens=Decimal("0"),
            amount_rmb=Decimal("0"),
            status_text="upstream_error",
            request_id=request_id,
            upstream_status_code=None,
            error_message=str(e),
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="上游请求失败")

    create_body = _safe_json(create_resp.content)
    if not (200 <= create_resp.status_code < 300):
        charge_and_record(
            db,
            user=user,
            endpoint="video.generate",
            tokens=Decimal("0"),
            amount_rmb=Decimal("0"),
            status_text="failed",
            request_id=request_id,
            upstream_status_code=create_resp.status_code,
            error_message=str(create_body)[:2000] if create_body is not None else create_resp.text[:2000],
        )
        return Response(
            content=create_resp.content,
            status_code=create_resp.status_code,
            media_type=create_resp.headers.get("content-type"),
        )

    task_id = None
    if isinstance(create_body, dict) and isinstance(create_body.get("id"), str):
        task_id = create_body.get("id")
    if not task_id:
        charge_and_record(
            db,
            user=user,
            endpoint="video.generate",
            tokens=Decimal("0"),
            amount_rmb=Decimal("0"),
            status_text="success",
            request_id=request_id,
            upstream_status_code=create_resp.status_code,
        )
        return Response(
            content=create_resp.content,
            status_code=create_resp.status_code,
            media_type=create_resp.headers.get("content-type"),
        )

    vt = db.query(VideoTask).filter(VideoTask.user_id == user.id, VideoTask.task_id == task_id).one_or_none()
    if not vt:
        vt = VideoTask(
            user_id=user.id,
            task_id=task_id,
            public_model=public_model.strip(),
            upstream_model=upstream_model,
            has_video_input=bool(has_video_input),
        )
        db.add(vt)
        db.commit()
        db.refresh(vt)

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    last_resp_content: bytes = b""
    last_status_code: int = 0

    while True:
        try:
            resp = await forward_json(
                method="GET",
                path=f"/api/v3/contents/generations/tasks/{task_id}",
                headers=upstream_headers,
                params={},
            )
        except Exception as e:
            logger.exception("upstream request failed", extra={"request_id": request_id})
            charge_and_record(
                db,
                user=user,
                endpoint="video.generate",
                tokens=Decimal("0"),
                amount_rmb=Decimal("0"),
                status_text="upstream_error",
                request_id=request_id,
                upstream_status_code=None,
                task_id=task_id,
                error_message=str(e),
            )
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="上游请求失败")

        last_resp_content = resp.content
        last_status_code = resp.status_code
        body = _safe_json(resp.content)

        if 200 <= resp.status_code < 300 and isinstance(body, dict):
            status_value = body.get("status")
            if isinstance(status_value, str):
                st = status_value.lower()
                if st == "succeeded":
                    content = body.get("content")
                    usage = body.get("usage")
                    video_url = None
                    if isinstance(content, dict) and isinstance(content.get("video_url"), str):
                        video_url = content.get("video_url")
                    total_tokens = None
                    if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
                        total_tokens = usage.get("total_tokens")

                    if bool(video_url) and isinstance(total_tokens, int) and total_tokens > 0:
                        if not vt.charged:
                            tokens_dec = Decimal(str(int(total_tokens)))
                            hv = bool(vt.has_video_input)
                            amount = quote_rmb(total_tokens=int(total_tokens), has_video_input=hv)
                            ensure_balance(db, user, Decimal(str(amount)))
                            charge_and_record(
                                db,
                                user=user,
                                endpoint="video.charge",
                                tokens=tokens_dec,
                                amount_rmb=Decimal(str(amount)),
                                status_text="success",
                                request_id=request_id,
                                upstream_status_code=resp.status_code,
                                task_id=task_id,
                            )
                            vt.charged = True
                            vt.charged_tokens = int(total_tokens)
                            vt.charged_amount_rmb = float(amount)
                            vt.charged_at = datetime.utcnow()
                            db.add(vt)
                            db.commit()

                        charge_and_record(
                            db,
                            user=user,
                            endpoint="video.generate",
                            tokens=Decimal("0"),
                            amount_rmb=Decimal("0"),
                            status_text="success",
                            request_id=request_id,
                            upstream_status_code=resp.status_code,
                            task_id=task_id,
                        )
                        return Response(
                            content=resp.content,
                            status_code=resp.status_code,
                            media_type=resp.headers.get("content-type"),
                        )

                if st in {"failed", "cancelled", "expired"}:
                    charge_and_record(
                        db,
                        user=user,
                        endpoint="video.generate",
                        tokens=Decimal("0"),
                        amount_rmb=Decimal("0"),
                        status_text=st,
                        request_id=request_id,
                        upstream_status_code=resp.status_code,
                        task_id=task_id,
                        error_message=str(body)[:2000],
                    )
                    return Response(
                        content=resp.content,
                        status_code=resp.status_code,
                        media_type=resp.headers.get("content-type"),
                    )

        if loop.time() >= deadline:
            charge_and_record(
                db,
                user=user,
                endpoint="video.generate",
                tokens=Decimal("0"),
                amount_rmb=Decimal("0"),
                status_text="timeout",
                request_id=request_id,
                upstream_status_code=last_status_code or None,
                task_id=task_id,
                error_message=(str(_safe_json(last_resp_content))[:2000] if last_resp_content else None),
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={"message": "等待视频任务结果超时", "task_id": task_id},
            )

        await asyncio.sleep(poll_interval_seconds)


@app.get("/v1/video/tasks/{task_id}")
async def get_video_task(
    task_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    request_id = _get_request_id(request)

    public_api_key = request.query_params.get("api_key")
    bearer = _resolve_upstream_bearer(db, public_api_key)

    params = dict(request.query_params)
    params.pop("api_key", None)

    upstream_headers = _build_upstream_headers(bearer)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "forward request_id=%s method=GET path=%s headers=%s params=%s",
            request_id,
            f"/api/v3/contents/generations/tasks/{task_id}",
            _redact_upstream_headers(upstream_headers),
            params,
        )

    try:
        resp = await forward_json(
            method="GET",
            path=f"/api/v3/contents/generations/tasks/{task_id}",
            headers=upstream_headers,
            params=params,
        )
    except Exception as e:
        logger.exception("upstream request failed", extra={"request_id": request_id})
        charge_and_record(
            db,
            user=user,
            endpoint="video.get",
            tokens=Decimal("0"),
            amount_rmb=Decimal("0"),
            status_text="upstream_error",
            request_id=request_id,
            upstream_status_code=None,
            task_id=task_id,
            error_message=str(e),
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="上游请求失败")

    body = _safe_json(resp.content)

    charged_now = False
    if 200 <= resp.status_code < 300 and isinstance(body, dict):
        status_value = body.get("status")
        content = body.get("content")
        usage = body.get("usage")
        video_url = None
        if isinstance(content, dict) and isinstance(content.get("video_url"), str):
            video_url = content.get("video_url")

        total_tokens = None
        if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
            total_tokens = usage.get("total_tokens")

        can_charge = (
            isinstance(status_value, str)
            and status_value.lower() == "succeeded"
            and bool(video_url)
            and isinstance(total_tokens, int)
            and total_tokens > 0
        )

        if can_charge:
            vt = (
                db.query(VideoTask)
                .filter(VideoTask.user_id == user.id, VideoTask.task_id == task_id)
                .one_or_none()
            )
            if not vt:
                vt = VideoTask(user_id=user.id, task_id=task_id, has_video_input=False)
                db.add(vt)
                db.commit()
                db.refresh(vt)

            if not vt.charged:
                tokens_dec = Decimal(str(int(total_tokens)))
                hv = bool(vt.has_video_input)
                amount_rmb = quote_rmb(total_tokens=int(total_tokens), has_video_input=hv)
                ensure_balance(db, user, Decimal(str(amount_rmb)))
                charge_and_record(
                    db,
                    user=user,
                    endpoint="video.charge",
                    tokens=tokens_dec,
                    amount_rmb=Decimal(str(amount_rmb)),
                    status_text="success",
                    request_id=request_id,
                    upstream_status_code=resp.status_code,
                    task_id=task_id,
                )
                vt.charged = True
                vt.charged_tokens = int(total_tokens)
                vt.charged_amount_rmb = float(amount_rmb)
                vt.charged_at = datetime.utcnow()
                db.add(vt)
                db.commit()
                charged_now = True

    charge_and_record(
        db,
        user=user,
        endpoint="video.get",
        tokens=Decimal("0"),
        amount_rmb=Decimal("0"),
        status_text="success" if 200 <= resp.status_code < 300 else "failed",
        request_id=request_id,
        upstream_status_code=resp.status_code,
        task_id=task_id,
        error_message=(
            None
            if 200 <= resp.status_code < 300
            else (str(body)[:2000] if body is not None else resp.text[:2000])
        ),
    )

    return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type"))


async def _cancel_impl(
    task_id: str,
    request: Request,
    db: Session,
    user: User,
):
    request_id = _get_request_id(request)
    public_api_key: Optional[str] = None
    try:
        raw_body = getattr(request.state, "raw_body", None)
        payload = _safe_json(raw_body) if isinstance(raw_body, (bytes, bytearray)) else await request.json()
        if isinstance(payload, dict) and isinstance(payload.get("api_key"), str):
            public_api_key = payload.get("api_key")
    except Exception:
        payload = None

    bearer = _resolve_upstream_bearer(db, public_api_key)

    upstream_headers = _build_upstream_headers(bearer)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "forward request_id=%s method=POST path=%s headers=%s body=%s",
            request_id,
            f"/api/v3/contents/generations/tasks/{task_id}/cancel",
            _redact_upstream_headers(upstream_headers),
            payload if isinstance(payload, dict) else None,
        )

    try:
        resp = await forward_json(
            method="POST",
            path=f"/api/v3/contents/generations/tasks/{task_id}/cancel",
            headers=upstream_headers,
            json_body=payload if isinstance(payload, dict) else None,
        )
    except Exception as e:
        logger.exception("upstream request failed", extra={"request_id": request_id})
        charge_and_record(
            db,
            user=user,
            endpoint="video.cancel",
            tokens=Decimal("0"),
            amount_rmb=Decimal("0"),
            status_text="upstream_error",
            request_id=request_id,
            upstream_status_code=None,
            task_id=task_id,
            error_message=str(e),
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="上游请求失败")

    body = _safe_json(resp.content)
    success = 200 <= resp.status_code < 300
    is_cancelled = False
    if isinstance(body, dict):
        status_value = body.get("status")
        if isinstance(status_value, str) and status_value.lower() == "cancelled":
            is_cancelled = True
        if body.get("cancelled") is True:
            is_cancelled = True

    if success:
        charge_and_record(
            db,
            user=user,
            endpoint="video.cancel",
            tokens=Decimal("0"),
            amount_rmb=Decimal("0"),
            status_text="success",
            request_id=request_id,
            upstream_status_code=resp.status_code,
            task_id=task_id,
        )
    else:
        charge_and_record(
            db,
            user=user,
            endpoint="video.cancel",
            tokens=Decimal("0"),
            amount_rmb=Decimal("0"),
            status_text="failed",
            request_id=request_id,
            upstream_status_code=resp.status_code,
            task_id=task_id,
            error_message=str(body)[:2000] if body is not None else resp.text[:2000],
        )

    return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type"))


@app.post("/v1/video/tasks/{task_id}/cancel")
async def cancel_video_task(
    task_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _cancel_impl(task_id, request, db, user)


@app.post("/v1/video/tasks/{task_id}:cancel")
async def cancel_video_task_alias(
    task_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _cancel_impl(task_id, request, db, user)


@app.get("/v1/usage")
def list_usage_records(
    limit: int = 50,
    offset: int = 0,
    charged_only: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    q = db.query(ConsumptionRecord).filter(ConsumptionRecord.user_id == user.id)
    if charged_only:
        q = q.filter(ConsumptionRecord.endpoint == "video.charge")
    q = q.order_by(ConsumptionRecord.id.desc()).offset(offset).limit(limit)
    items = []
    for r in q.all():
        has_video_input = None
        rmb_per_million = None
        amount_rmb = float(r.amount_rmb) if r.amount_rmb is not None else 0.0
        if r.task_id:
            vt = (
                db.query(VideoTask)
                .filter(VideoTask.user_id == user.id, VideoTask.task_id == r.task_id)
                .one_or_none()
            )
            if vt:
                has_video_input = bool(vt.has_video_input)
        if r.endpoint == "video.charge":
            hv = bool(has_video_input) if has_video_input is not None else False
            cfg = get_config()
            rmb_per_million = (
                cfg.pricing.money.with_video_input_rmb_per_million
                if hv
                else cfg.pricing.money.without_video_input_rmb_per_million
            )
            if not amount_rmb:
                amount_rmb = float(
                    quote_rmb(total_tokens=int(float(r.tokens_charged)), has_video_input=hv)
                )

        items.append(
            {
                "id": r.id,
                "endpoint": r.endpoint,
                "task_id": r.task_id,
                "request_id": r.request_id,
                "tokens_charged": float(r.tokens_charged),
                "amount_rmb": amount_rmb,
                "rmb_per_million_tokens": float(rmb_per_million) if rmb_per_million is not None else None,
                "has_video_input": has_video_input,
                "balance_before": float(r.balance_before),
                "balance_after": float(r.balance_after),
                "status": r.status,
                "upstream_status_code": r.upstream_status_code,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() + "Z",
            }
        )
    return {"items": items, "limit": limit, "offset": offset}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/v1/billing/quote")
async def billing_quote(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请求体必须是JSON对象")

    total_tokens = None
    if isinstance(payload.get("total_tokens"), int):
        total_tokens = payload.get("total_tokens")
    usage = payload.get("usage")
    if total_tokens is None and isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
        total_tokens = usage.get("total_tokens")
    if total_tokens is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少total_tokens")

    has_video_input = None
    if isinstance(payload.get("has_video_input"), bool):
        has_video_input = payload.get("has_video_input")
    if has_video_input is None:
        has_video_input = detect_video_input(payload)

    amount = quote_rmb(total_tokens=int(total_tokens), has_video_input=bool(has_video_input))
    cfg = get_config()
    price = (
        cfg.pricing.money.with_video_input_rmb_per_million
        if has_video_input
        else cfg.pricing.money.without_video_input_rmb_per_million
    )
    return {
        "total_tokens": int(total_tokens),
        "has_video_input": bool(has_video_input),
        "rmb_per_million_tokens": float(price),
        "amount_rmb": float(amount),
    }
