from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
import logging
import json
from typing import Any, Dict, Optional
from app.config import get_config

logger = logging.getLogger("allapi")

def _redact_token(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= 10:
        return "***"
    return v[:4] + "..." + v[-4:]

def _redact_headers(headers: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in {"authorization", "x-user-token"}:
            out[k] = _redact_token(v)
        else:
            out[k] = v
    return out

def _make_client() -> httpx.AsyncClient:
    cfg = get_config()
    timeout = httpx.Timeout(cfg.upstream.timeout_seconds)
    return httpx.AsyncClient(timeout=timeout)


async def forward_json(
    *,
    method: str,
    path: str,
    headers: Dict[str, str],
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Any] = None,
):
    cfg = get_config()
    url = cfg.upstream.base_url.rstrip("/") + "/" + path.lstrip("/")
    
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "upstream request: method=%s url=%s headers=%s params=%s body=%s",
            method,
            url,
            _redact_headers(headers),
            params,
            json.dumps(json_body) if json_body else None,
        )
        
    async with _make_client() as client:
        resp = await client.request(method, url, headers=headers, params=params, json=json_body)
    
    if logger.isEnabledFor(logging.DEBUG):
        try:
            resp_body = resp.json()
        except Exception:
            resp_body = resp.text[:2000]
        logger.debug(
            "upstream response: status=%s headers=%s body=%s",
            resp.status_code,
            _redact_headers(dict(resp.headers)),
            resp_body,
        )
        
    return resp
