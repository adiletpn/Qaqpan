"""AI calls through the xKiro gateway, behind a disk cache.

Provider: xKiro (https://docs.xkiro.com), OpenAI-compatible chat completions endpoint,
default model Mistral Medium 3.5 (free tier, accepts images, best Kazakh among free models we tested). Configure in .env:
    XKIRO_API_KEY=sk-xt-...            required for live calls
    XKIRO_MODEL=mistralai/mistral-medium-3.5
    XKIRO_BASE_URL=https://api.xkiro.com/v1

Order: cache -> live call (timeout, spend limits) -> None (caller falls back to rules/templates).
QAQPAN_DEMO=1 forbids live calls: the stage demo must not depend on the network.
Cache files live in data/llm_cache/ and are committed, so the deployed demo has them too.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import deque
from datetime import date
from pathlib import Path
from typing import Callable, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

log = logging.getLogger("qaqpan.llm")

ROOT = Path(__file__).resolve().parent.parent
try:  # local secrets live in .env (git-ignored); real environment variables win
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except ImportError:  # pragma: no cover
    pass

CACHE_DIR = ROOT / "data" / "llm_cache"
BASE_URL = os.getenv("XKIRO_BASE_URL", "https://api.xkiro.com/v1").rstrip("/")
MODEL = os.getenv("XKIRO_MODEL", "mistralai/mistral-medium-3.5")
TIMEOUT_S = float(os.getenv("QAQPAN_LLM_TIMEOUT", "25"))
# Spend/abuse guard for a public link: beyond these limits answers come from rules/templates.
RPM = int(os.getenv("QAQPAN_LLM_RPM", "20"))
DAILY = int(os.getenv("QAQPAN_LLM_DAILY", "500"))

M = TypeVar("M", bound=BaseModel)

_disabled_reason: str | None = None
_guard = threading.Lock()
_recent: deque[float] = deque()
_daily: dict[date, int] = {}


def _api_key() -> str | None:
    return os.getenv("XKIRO_API_KEY") or None


def _allow_live_call() -> bool:
    now = time.time()
    with _guard:
        while _recent and now - _recent[0] > 60:
            _recent.popleft()
        today = date.today()
        if len(_recent) >= RPM or _daily.get(today, 0) >= DAILY:
            return False
        _recent.append(now)
        _daily[today] = _daily.get(today, 0) + 1
        return True


def demo_mode() -> bool:
    return os.getenv("QAQPAN_DEMO") == "1"


def status() -> dict:
    return {"provider": "xkiro", "model": MODEL, "key": bool(_api_key()), "demo_mode": demo_mode(),
            "live_disabled": _disabled_reason, "calls_today": _daily.get(date.today(), 0), "daily_limit": DAILY}


def _key(kind: str, payload: dict) -> str:
    raw = json.dumps({**payload, "model": MODEL}, sort_keys=True, ensure_ascii=False).encode()
    return f"{kind}-{hashlib.sha256(raw).hexdigest()[:20]}"


class Unavailable(Exception):
    """Live call not possible right now (no key, network, rate limit, bad answer)."""


def cached_call(kind: str, payload: dict, model_cls: type[M], call: Callable[[], M | None],
                allow_in_demo: bool = False) -> tuple[M | None, str]:
    """Returns (result, source) where source is 'cache' | 'llm' | 'unavailable'.

    allow_in_demo: the conversational assistant may call the model live even on stage — it has an
    offline fallback, so a network failure costs nothing but a simpler answer.
    """
    path = CACHE_DIR / f"{_key(kind, payload)}.json"
    if path.exists():
        try:
            return model_cls.model_validate_json(path.read_text()), "cache"
        except ValidationError:  # stale cache entry: ignore and recompute
            log.warning("bad cache entry %s", path.name)
    if (demo_mode() and not allow_in_demo) or _disabled_reason or not _api_key() or not _allow_live_call():
        return None, "unavailable"
    try:
        result = call()
    except Unavailable as e:
        log.warning("llm unavailable: %s", e)
        return None, "unavailable"
    if result is None:
        return None, "unavailable"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2))
    return result, "llm"


def _post(body: dict) -> dict:
    """One chat-completions request. Disables live calls for the process on auth errors."""
    global _disabled_reason
    try:
        r = httpx.post(f"{BASE_URL}/chat/completions", json=body, timeout=TIMEOUT_S,
                       headers={"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"})
    except httpx.HTTPError as e:
        raise Unavailable(f"network: {e}") from e
    if r.status_code in (401, 403):
        _disabled_reason = f"auth: HTTP {r.status_code}"
        raise Unavailable(_disabled_reason)
    if r.status_code >= 400:
        raise Unavailable(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def _extract_json(text: str) -> str:
    m = re.search(r"\{.*\}", text, re.S)  # tolerate code fences or a sentence around the object
    if not m:
        raise Unavailable("no JSON object in the answer")
    return m.group(0)


def parse(system: str, text: str | None, model_cls: type[M], example: str, image_b64: str | None = None,
          media_type: str = "image/png", max_tokens: int = 1500) -> M | None:
    """Structured answer: the model must return a JSON object shaped like `example`.

    A filled-in example works better than a JSON schema: weaker models tend to echo a schema back.
    """
    if image_b64:
        user: str | list[dict] = [
            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
            {"type": "text", "text": text or "Проверь сообщение на изображении."},
        ]
    else:
        user = text or ""
    body = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": f"{system}\n\nОтветь ТОЛЬКО одним JSON-объектом такого вида (значения замени своими), "
                                          f"без пояснений и без markdown:\n{example}"},
            {"role": "user", "content": user},
        ],
    }
    data = _post(body)
    choice = (data.get("choices") or [{}])[0]
    if choice.get("finish_reason") == "content_filter":
        return None
    raw = (choice.get("message") or {}).get("content") or ""
    try:
        return model_cls.model_validate_json(_extract_json(raw))
    except ValidationError as e:
        raise Unavailable(f"answer does not match schema: {e.errors()[:2]}") from e


def chat(system: str, history: list[dict], max_tokens: int = 400) -> str | None:
    """Free-text conversation turn (assistant). history: [{"role": "user"|"assistant", "content": str}]."""
    body = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.4,
        "messages": [{"role": "system", "content": system}] + [
            {"role": m["role"], "content": m["content"]} for m in history if m.get("role") in ("user", "assistant")],
    }
    data = _post(body)
    choice = (data.get("choices") or [{}])[0]
    if choice.get("finish_reason") == "content_filter":
        return None
    return (choice.get("message") or {}).get("content")
