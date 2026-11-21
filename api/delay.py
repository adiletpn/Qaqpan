"""«Отложить на час»: the transfer waits an hour, and Qaqpan analyses the whole session meanwhile.

The AI reads the session (call, checked messages, call checks, transfer attempts, the recipient) and picks a
verdict and reason CODES from a fixed list; the client sees only approved texts for those codes
(api/texts.py, DELAY_REASONS) — «ИИ выбирает, комплаенс утверждает тексты». Like the message check, the AI may
make the verdict stricter than the rules, never softer. Without the model the rules decide.
"""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, Field

from . import llm
from .state import State, Transfer
from .texts import DELAY_REASONS, t

Verdict = Literal["likely_scam", "unclear", "likely_ok"]
SEVERITY = {"likely_ok": 0, "unclear": 1, "likely_scam": 2}
CODES = tuple(DELAY_REASONS)
PROMPT_VERSION = 1


def facts(st: State, tr: Transfer) -> dict[str, bool]:
    """What Qaqpan knows — coarse booleans, so the same situation hits the same cache entry."""
    since = time.time() - 3 * 3600
    alerts = [a.text["ru"] for a in st.alerts.get(tr.client_id, []) if a.ts >= since]
    r = set(tr.reasons)
    attempts = sum(1 for x in st.transfers.values() if x.client_id == tr.client_id and time.time() - x.ts < 24 * 3600
                   and not st.is_known(tr.client_id, x.account))
    return {
        "PRESSURE_CALL": tr.pressure,
        "SCAM_MESSAGE_TODAY": any("мошенничество" in a for a in alerts),
        "BANK_NOT_CALLING": any("банк не звонит" in a for a in alerts),
        "NEW_RECIPIENT": "NEW_RECIPIENT" in r,
        "LARGE_SHARE": "BIG_SHARE" in r,
        "RECIPIENT_REPORTED": bool(r & {"RECIPIENT_COMPLAINTS", "RECIPIENT_SIGNALS", "RECIPIENT_AFC"}),
        "REPEATED_ATTEMPTS": attempts >= 2,
        "OWN_OTHER_BANK": "OWN_OTHER_BANK" in r,
        "LOAN_FRESH": "LOAN_FRESH" in r,
    }


def rules(f: dict[str, bool]) -> tuple[Verdict, list[str]]:
    codes = [c for c in CODES if f.get(c)]
    context = f["SCAM_MESSAGE_TODAY"] or f["BANK_NOT_CALLING"] or f["OWN_OTHER_BANK"] or f["RECIPIENT_REPORTED"]
    if (f["PRESSURE_CALL"] and (context or f["LARGE_SHARE"])) or f["RECIPIENT_REPORTED"] and f["NEW_RECIPIENT"] or f["LOAN_FRESH"]:
        return "likely_scam", codes
    if codes and codes != ["NEW_RECIPIENT"]:
        return "unclear", codes
    return "likely_ok", codes or ["NO_RISK_SIGNS"]


class AiAnalysis(BaseModel):
    verdict: Verdict
    codes: list[str] = Field(description="2-4 reason codes from the list, most important first")


SYSTEM = """Ты — аналитик антифрода банка в Казахстане. Клиент отложил перевод на час. По фактам сессии реши,
похоже ли это на мошенничество: likely_scam (похоже на обман), unclear (есть сомнения), likely_ok (явных
признаков нет). Учитывай сочетание признаков: звонок «из банка» + перевод новому получателю + сегодняшнее
мошенническое SMS — это классическая схема. Выбери от 2 до 4 кодов причин ТОЛЬКО из списка и только тех, что
верны по фактам, самые важные первыми. Текст тебе писать не нужно — тексты для клиента утверждены банком."""

EXAMPLE = '{"verdict": "likely_scam", "codes": ["PRESSURE_CALL", "BANK_NOT_CALLING"]}  — codes: ' + ", ".join(CODES)


def analyse(st: State, tr: Transfer, lang: str) -> dict:
    f = facts(st, tr)
    verdict, codes = rules(f)
    source = "rules"
    payload = {"facts": f, "amount_band": "big" if tr.amount >= 500_000 else "mid" if tr.amount >= 100_000 else "small",
               "v": PROMPT_VERSION}
    prompt = "Факты сессии:\n" + "\n".join(f"- {k}: {'да' if v else 'нет'}" for k, v in f.items()) + \
             f"\n- сумма: {payload['amount_band']}"
    ai, src = llm.cached_call("delay", payload, AiAnalysis, lambda: llm.parse(SYSTEM, prompt, AiAnalysis, EXAMPLE, max_tokens=200))
    if ai is not None:
        picked = [c for c in ai.codes if c in CODES and (f.get(c) or c == "NO_RISK_SIGNS" and not any(f.values()))]
        if SEVERITY[ai.verdict] >= SEVERITY[verdict]:  # stricter or equal: trust the AI's reading of the situation
            verdict = ai.verdict
        codes = picked or codes
        source = "cache" if src == "cache" else "llm"
    codes = codes[:4]
    return {"verdict": verdict, "codes": codes, "source": source, "facts": f}


def view(analysis: dict | None, lang: str) -> dict | None:
    if not analysis:
        return None
    v = analysis["verdict"]
    return {"verdict": v, "title": t(f"delay.{v}.title", lang), "advice": t(f"delay.{v}.advice", lang),
            "reasons": [DELAY_REASONS[c][lang] for c in analysis["codes"]], "source": analysis["source"]}
