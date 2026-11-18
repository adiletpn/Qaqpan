"""Layer 3 «Уговорили перевести»: transfer risk scoring.

Transparent weighted rules (every point of score has a reason code). In production the same
features feed a model trained on the bank's labelled transfers; the reason codes stay.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .state import Account, Client

WEIGHTS = {
    "CALL_ACTIVE": 0.35,
    "RECIPIENT_COMPLAINTS": 0.5,
    "RECIPIENT_AFC": 0.6,
    "NEW_RECIPIENT": 0.15,
    "BIG_SHARE": 0.15,      # >= 50% of balance (+0.1 more at >= 80%)
    "BIG_AMOUNT": 0.1,      # >= 500 000 ₸
    "NIGHT": 0.1,           # 00:00–06:00
    "PASTED": 0.05,
    "APP_SWITCH": 0.1,      # >= 2 switches to another app while filling the form
    "OWN_OTHER_BANK": 0.15,  # «move it to your own card in another bank first» during a call
    "KNOWN_RECIPIENT": -0.3,  # not applied during a call: scammers use the victim's own accounts as a first hop
}
LEVEL_WARN = 0.3
LEVEL_HOLD = 0.5


@dataclass
class Assessment:
    score: float
    level: int
    reasons: list[str]
    kw: dict
    template: str


def assess(client: Client, acc: Account, amount: float, on_call: bool, pasted: bool, app_switches: int,
           now: datetime | None = None) -> Assessment:
    now = now or datetime.now()
    reasons: list[str] = []
    kw: dict = {}
    score = 0.0

    def add(code: str, w: float | None = None) -> None:
        nonlocal score
        score += WEIGHTS[code] if w is None else w
        reasons.append(code)

    known = acc.number in client.known_accounts
    if on_call:
        add("CALL_ACTIVE")
        if acc.owner_id == client.id and acc.bank != "BCC":
            add("OWN_OTHER_BANK")
    if acc.in_afc:
        add("RECIPIENT_AFC")
    if acc.complaints > 0:
        add("RECIPIENT_COMPLAINTS")
    if not known:
        add("NEW_RECIPIENT")
    elif not on_call:
        add("KNOWN_RECIPIENT")
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
    template = "call" if on_call else "purchase" if (acc.complaints or acc.in_afc) else "generic"
    return Assessment(round(score, 2), level, reasons, kw, template)
