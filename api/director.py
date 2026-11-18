"""Demo director: scripted events for the stage (docs/DEMO_SCENARIO.md).

In production these events come from the real world (SMS, calls, the bank's call log);
here the presenter triggers them from /director or with hotkeys on /stage.
"""

from __future__ import annotations

import time

from . import msgcheck
from .state import BANK_NUMBER, SCAM_NUMBER, STATE, Call, Sms

DEMO_ACCOUNT = "KZ86 8562 0000 0471 1934"
ACTIONS = ("reset", "sms", "call", "end_call", "transfer_aigerim", "transfer_madina", "bank_calls_madina", "victim")


def run(action: str) -> None:
    """Apply one scripted event. Raises KeyError for unknown actions."""
    now = time.time()
    with STATE.lock:
        if action == "reset":
            STATE.reset()
        elif action == "sms":
            STATE.sms["aigerim"].append(Sms(STATE.new_id("SMS"), "eGov", msgcheck.load_samples().get("ecp", {}).get(
                "text", "Срок действия вашей ЭЦП истекает сегодня. Продлите: egov-kz.online/ecp"), "ecp", now))
            STATE.emit("director", "aigerim", "Айгерим получила SMS «ЭЦП истекает»")
        elif action == "call":
            STATE.calls["aigerim"] = Call(SCAM_NUMBER, SCAM_NUMBER, now)
            STATE.emit("director", "aigerim", f"Айгерим звонят с {SCAM_NUMBER} («служба безопасности банка»)")
        elif action == "end_call":
            STATE.end_call("aigerim")
        elif action == "transfer_aigerim":
            STATE.prefill["aigerim"] = {"account": DEMO_ACCOUNT, "amount": 900_000}
            STATE.nav["aigerim"] = {"screen": "transfer", "seq": int(now * 1000)}
        elif action == "transfer_madina":
            STATE.prefill["madina"] = {"account": DEMO_ACCOUNT, "amount": 150_000, "note": "iPhone 15 · OLX"}
            STATE.nav["madina"] = {"screen": "transfer", "seq": int(now * 1000)}
        elif action == "bank_calls_madina":
            STATE.calls["madina"] = Call(BANK_NUMBER, "BCC · 505", now, is_bank=True)
            STATE.bank_outbound["madina"] = Call(BANK_NUMBER, "BCC", now, is_bank=True,
                                                 employee="Асем Нурланова", department="отдел кредитования")
            STATE.emit("director", "madina", "Мадине звонит настоящий сотрудник банка (505)")
        elif action == "victim":
            STATE.nav["aigerim"] = {"screen": "victim", "seq": int(now * 1000)}
        else:
            raise KeyError(action)
