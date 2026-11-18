"""Claude calls behind a disk cache.

Order: cache -> live call (with timeout) -> None (caller falls back to rules/templates).
QALQAN_DEMO=1 forbids live calls: the stage demo must not depend on the network.
Cache files live in data/llm_cache/ and are committed, so the deployed demo has them too.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import deque
from datetime import date
from pathlib import Path
from typing import Callable, TypeVar

from pydantic import BaseModel

log = logging.getLogger("qalqan.llm")

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "llm_cache"
MODEL = os.getenv("QALQAN_MODEL", "claude-opus-5-5")
TIMEOUT_S = float(os.getenv("QALQAN_LLM_TIMEOUT", "25"))
# Spend guard for a public link: beyond these limits answers come from rules/templates.
RPM = int(os.getenv("QALQAN_LLM_RPM", "20"))
DAILY = int(os.getenv("QALQAN_LLM_DAILY", "500"))

M = TypeVar("M", bound=BaseModel)

_client = None
_disabled_reason: str | None = None
_guard = threading.Lock()
_recent: deque[float] = deque()
_daily: dict[date, int] = {}


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
    return os.getenv("QALQAN_DEMO") == "1"


def status() -> dict:
    return {"model": MODEL, "demo_mode": demo_mode(), "live_disabled": _disabled_reason,
            "calls_today": _daily.get(date.today(), 0), "daily_limit": DAILY}


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=1)
    return _client


def _key(kind: str, payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return f"{kind}-{hashlib.sha256(raw).hexdigest()[:20]}"


def cached_call(kind: str, payload: dict, model_cls: type[M], call: Callable[[], M]) -> tuple[M | None, str]:
    """Returns (result, source) where source is 'cache' | 'llm' | 'unavailable'."""
    global _disabled_reason
    path = CACHE_DIR / f"{_key(kind, payload)}.json"
    if path.exists():
        try:
            return model_cls.model_validate_json(path.read_text()), "cache"
        except Exception:  # corrupted cache entry: ignore and recompute
            log.warning("bad cache entry %s", path.name)
    if demo_mode() or _disabled_reason or not _allow_live_call():
        return None, "unavailable"
    import anthropic

    try:
        result = call()
    except anthropic.AuthenticationError as e:
        _disabled_reason = f"auth: {e.message}"
        return None, "unavailable"
    except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.APIStatusError) as e:
        log.warning("llm call failed: %s", e)
        return None, "unavailable"
    except TypeError as e:  # SDK raises TypeError when no credentials can be resolved at all
        _disabled_reason = f"no credentials: {e}"
        return None, "unavailable"
    if result is None:
        return None, "unavailable"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2))
    return result, "llm"


def parse(system: str, content: list[dict], model_cls: type[M], max_tokens: int = 4000, effort: str = "low") -> M | None:
    """One structured-output request. Server-side fallback is enabled for refusals."""
    resp = _get_client().beta.messages.parse(
        model=MODEL,
        max_tokens=max_tokens,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": effort},
        system=system,
        messages=[{"role": "user", "content": content}],
        output_format=model_cls,
    )
    if resp.stop_reason == "refusal":
        return None
    return resp.parsed_output
