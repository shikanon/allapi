from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import os
import json

import yaml
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///./data/app.db"


class AuthConfig(BaseModel):
    header: str = "Authorization"
    bearer_prefix: str = "Bearer"


class UpstreamConfig(BaseModel):
    base_url: str = "https://ark.cn-beijing.volces.com"
    timeout_seconds: int = 60
    default_bearer_token: str = ""
    api_key_mapping: Dict[str, str] = Field(default_factory=dict)
    model_mapping: Dict[str, str] = Field(default_factory=dict)


class PricingMoneyConfig(BaseModel):
    with_video_input_rmb_per_million: float = 28.0
    without_video_input_rmb_per_million: float = 46.0


class PricingConfig(BaseModel):
    money: PricingMoneyConfig = Field(default_factory=PricingMoneyConfig)


class AppSectionConfig(BaseModel):
    environment: str = "dev"
    log_level: str = "INFO"


class AppConfig(BaseModel):
    app: AppSectionConfig = Field(default_factory=AppSectionConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    upstream: UpstreamConfig = Field(default_factory=UpstreamConfig)
    pricing: PricingConfig = Field(default_factory=PricingConfig)


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        content = yaml.safe_load(f) or {}
    if not isinstance(content, dict):
        return {}
    return content


def _parse_mapping_env(value: str) -> Dict[str, str]:
    raw = (value or "").strip()
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            out: Dict[str, str] = {}
            for k, v in obj.items():
                if isinstance(k, str) and isinstance(v, str):
                    out[k] = v
            return out
    except Exception:
        pass

    out: Dict[str, str] = {}
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    for part in parts:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k and v:
            out[k] = v
    return out


def _apply_env_overrides(raw: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(raw)

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        merged.setdefault("database", {})
        merged["database"]["url"] = database_url

    upstream_base_url = os.getenv("UPSTREAM_BASE_URL")
    if upstream_base_url:
        merged.setdefault("upstream", {})
        merged["upstream"]["base_url"] = upstream_base_url

    upstream_timeout = os.getenv("UPSTREAM_TIMEOUT_SECONDS")
    if upstream_timeout:
        try:
            merged.setdefault("upstream", {})
            merged["upstream"]["timeout_seconds"] = int(upstream_timeout)
        except Exception:
            pass

    default_bearer = os.getenv("UPSTREAM_DEFAULT_BEARER_TOKEN")
    if default_bearer is not None and default_bearer != "":
        merged.setdefault("upstream", {})
        merged["upstream"]["default_bearer_token"] = default_bearer

    api_key_mapping = os.getenv("UPSTREAM_API_KEY_MAPPING")
    if api_key_mapping:
        merged.setdefault("upstream", {})
        merged["upstream"]["api_key_mapping"] = _parse_mapping_env(api_key_mapping)

    model_mapping = os.getenv("UPSTREAM_MODEL_MAPPING")
    if model_mapping:
        merged.setdefault("upstream", {})
        merged["upstream"]["model_mapping"] = _parse_mapping_env(model_mapping)

    with_video_rmb = os.getenv("BILLING_RMB_PER_MILLION_WITH_VIDEO_INPUT")
    if with_video_rmb:
        try:
            merged.setdefault("pricing", {})
            merged.setdefault("pricing", {}).setdefault("money", {})
            merged["pricing"].setdefault("money", {})["with_video_input_rmb_per_million"] = float(
                with_video_rmb
            )
        except Exception:
            pass

    without_video_rmb = os.getenv("BILLING_RMB_PER_MILLION_WITHOUT_VIDEO_INPUT")
    if without_video_rmb:
        try:
            merged.setdefault("pricing", {})
            merged.setdefault("pricing", {}).setdefault("money", {})
            merged["pricing"].setdefault("money", {})[
                "without_video_input_rmb_per_million"
            ] = float(without_video_rmb)
        except Exception:
            pass

    return merged


@lru_cache
def get_config() -> AppConfig:
    config_path = Path(os.getenv("CONFIG_PATH", "config.yaml"))
    raw = _load_yaml(config_path)
    raw = _apply_env_overrides(raw)
    return AppConfig.model_validate(raw)
