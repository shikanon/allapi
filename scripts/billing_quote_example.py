from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx


def main():
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:8001").rstrip("/")
    user_token = os.getenv("USER_TOKEN", "").strip()
    if not user_token:
        raise SystemExit("missing USER_TOKEN")

    total_tokens = int(os.getenv("TOTAL_TOKENS", "108900"))
    has_video_input = os.getenv("HAS_VIDEO_INPUT", "true").lower() in {"1", "true", "yes"}

    payload = {"total_tokens": total_tokens, "has_video_input": has_video_input}
    headers = {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}

    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{base_url}/v1/billing/quote", headers=headers, json=payload)
        resp.raise_for_status()
        print(json.dumps(resp.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
