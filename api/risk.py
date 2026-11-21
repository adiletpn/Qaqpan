"""Layer 3 «Уговорили перевести»: transfer risk scoring.

Transparent weighted rules (every point of score has a reason code). In production the same
features feed a model trained on the bank's labelled transfers; the reason codes stay.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .state import Account, Client

WEIGHTS = {
    "CALL_ACTIVE": 0.35,
    "RECENT_CALL": 0.35,    # «положите трубку и переведите сами»: a call ended < 30 min ago weighs like an active one
    "RECIPIENT_COMPLAINTS": 0.5,
    "RECIPIENT_AFC": 0.6,
    "RECIPIENT_SIGNALS": 0.15,  # unconfirmed signals (a complaint without a stopped transfer, a guardian's «no»)
    "NEW_RECIPIENT": 0.15,
    "BIG_SHARE": 0.15,      # >= 50% of balance (+0.1 more at >= 80%)
    "BIG_AMOUNT": 0.1,      # >= 500 000 ₸
    "NIGHT": 0.1,           # 00:00–06:00
    "PASTED": 0.05,
    "APP_SWITCH": 0.1,      # >= 2 switches to another app while filling the form
    "OWN_OTHER_BANK": 0.15,  # «move it to your own card in another bank first» during a call
    "LOAN_FRESH": 0.35,     # >= half of a loan issued < 72 h ago goes to a new recipient («оформите кредит и переведите»)
    "KNOWN_RECIPIENT": -0.3,  # not applied during a call: scammers use the victim's own accounts as a first hop
}
LEVEL_WARN = 0.3
LEVEL_HOLD = 0.5
ALMATY = timezone(timedelta(hours=5))  # Kazakhstan is on a single UTC+5 since 2024; containers run in UTC
LOAN_FRESH_S = 72 * 3600


def local_now() -> datetime:
    return datetime.now(ALMATY)


@dataclass
class Assessment:
    score: float
    level: int
    reasons: list[str]
    kw: dict
    template: str


def assess(client: Client, acc: Account, amount: float, on_call: bool, pasted: bool, app_switches: int,
           now: datetime | None = None, *, recent_call: bool = False, known: bool | None = None,
           loan: tuple[float, float] | None = None, ts: float | None = None) -> Assessment:
    """recent_call: a call ended less than 30 min ago; known: recipient paid before the last 24 h (computed by the
    caller from the session; defaults to the client's long-standing recipients); loan: (amount, issued_ts)."""
    now = now or local_now()
    reasons: list[str] = []
    kw: dict = {}
    score = 0.0

    def add(code: str, w: float | None = None) -> None:
        nonlocal score
        score += WEIGHTS[code] if w is None else w
        reasons.append(code)

    if known is None:
        known = acc.number in client.known_accounts
    pressure = on_call or recent_call
    if on_call:
        add("CALL_ACTIVE")
    elif recent_call:
        add("RECENT_CALL")
    if pressure and acc.owner_id == client.id and acc.bank != "BCC":
        add("OWN_OTHER_BANK")
    if acc.in_afc:
        add("RECIPIENT_AFC")
    if acc.complaints > 0:
        add("RECIPIENT_COMPLAINTS")
    elif acc.signals > 0:
        add("RECIPIENT_SIGNALS")
    if not known:
        add("NEW_RECIPIENT")
    elif not pressure:
        add("KNOWN_RECIPIENT")
    if loan and not known and ts is not None and ts - loan[1] < LOAN_FRESH_S and amount >= 0.5 * loan[0]:
        add("LOAN_FRESH")
    share = amount / client.balance if client.balance > 0 else 1.0
    if share >= 0.5:
        add("BIG_SHARE", WEIGHTS["BIG_SHARE"] + (0.1 if share >= 0.8 else 0.0))
        kw["pct"] = round(share * 100)
    if amount >= 500_000:
        add("BIG_AMOUNT")
    if 0 <= now.hour < 6:
        add("NIGHT")
    if pasted:
        add("PASTED")
    if app_switches >= 2:
        add("APP_SWITCH")

    score = max(0.0, min(1.0, score))
    level = 2 if score >= LEVEL_HOLD else 1 if score >= LEVEL_WARN else 0
    template = "call" if pressure else "purchase" if (acc.complaints or acc.in_afc) else "generic"
    return Assessment(round(score, 2), level, reasons, kw, template)
