from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from app.config import get_config


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
    async with _make_client() as client:
        resp = await client.request(method, url, headers=headers, params=params, json=json_body)
    return resp
