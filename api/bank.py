"""The bank's side: the antifraud analyst console.

Qaqpan complements the bank's antifraud, it does not replace it. This module is what an analyst at BCC sees:
  * a queue of transfers Qaqpan stopped, delayed or sent to the family — with reason codes, the client's session
    timeline and a short AI summary written for the analyst (staff text, so free AI text is fine here);
  * a drop-account detector — money from several different clients into one account within 24 h, complaints,
    a fresh account — the AFM counts 112 bn ₸ through droppers' accounts in 2026;
  * a behavioural baseline per client — «900 000 is 72 times her usual spending».
The client never sees any of this about another person's account (banking secrecy): only «на этот счёт
поступали жалобы» or «счёт под наблюдением банка».
"""

from __future__ import annotations

import threading
import time

from pydantic import BaseModel

from . import llm
from .state import State, Transfer
from .texts import REASONS

DAY = 24 * 3600
DROP_FLAG = 0.6
DROP_WATCH = 0.35
ACTIVE = ("held", "escalated", "delayed", "awaiting_family")


def _fmt(amount: float) -> str:
    return f"{amount:,.0f} ₸".replace(",", " ")


# ---------------------------------------------------------------- behavioural baseline

def typical_spend(st: State, cid: str) -> float | None:
    """The client's usual largest payment: card history plus completed transfers (no history -> no baseline)."""
    outs = [-h["amount"] for h in st.history.get(cid, []) if h["amount"] < 0]
    outs += [t.amount for t in st.transfers.values() if t.client_id == cid and t.status == "completed"]
    return max(outs) if outs else None


# ---------------------------------------------------------------- drop accounts

def drop_profile(st: State, number: str, now: float | None = None) -> dict:
    """How much an account looks like a money mule's ('дроп'): weighted, explainable signals."""
    now = now or time.time()
    acc = st.accounts.get(number)
    attempts = [t for t in st.transfers.values() if t.account == number and now - t.ts < DAY]
    senders = {t.client_id for t in attempts}
    owned = bool(acc and acc.owner_id)
    known_somewhere = any(number in c.known_accounts for c in st.clients.values())
    signals: list[str] = []
    score = 0.0
    if len(senders) >= 2:
        score += 0.35
        signals.append(f"переводы от {len(senders)} разных клиентов за сутки")
    if len(senders) >= 3:
        score += 0.2
    if acc and acc.complaints:
        score += 0.3
        signals.append(f"подтверждённые жалобы: {acc.complaints}")
    if acc and acc.signals:
        score += 0.1
        signals.append(f"непроверенные сигналы: {acc.signals}")
    if acc and acc.in_afc:
        score += 0.4
        signals.append("в базе Антифрод-центра")
    if attempts and not known_somewhere and not owned:
        score += 0.1
        signals.append("новый для наших клиентов счёт")
    score = min(1.0, score)
    label = "drop" if score >= DROP_FLAG else "watch" if score >= DROP_WATCH else "ok"
    flows: dict[str, float] = {}
    for t in attempts:  # who sent how much: staff-only, the client never sees another person's operations
        flows[t.client_id] = flows.get(t.client_id, 0) + t.amount
    return {"account": number, "display": acc.display if acc else number, "holder": acc.holder if acc else "",
            "bank": acc.bank if acc else "", "score": round(score, 2), "label": label, "signals": signals,
            "senders": len(senders), "inflow": sum(t.amount for t in attempts), "attempts": len(attempts),
            "flows": [{"name": st.clients[c].short, "amount": a} for c, a in sorted(flows.items(), key=lambda x: -x[1])]}


def drops(st: State) -> list[dict]:
    seen = {t.account for t in st.transfers.values()} | {a.number for a in st.accounts.values() if a.complaints or a.in_afc}
    out = [drop_profile(st, n) for n in seen]
    return sorted([d for d in out if d["label"] != "ok"], key=lambda d: -d["score"])


# ---------------------------------------------------------------- analyst notes

class AnalystNote(BaseModel):
    summary: str


SYSTEM = """Ты помогаешь аналитику антифрода банка в Казахстане. По фактам об остановленном переводе напиши
2–3 коротких предложения по-русски: что произошло, на какую известную схему это похоже и что проверить
в первую очередь. Пиши для сотрудника банка, без воды и без обращения к клиенту. Не выдумывай фактов."""
EXAMPLE = '{"summary": "Клиентка во время звонка «службы безопасности» переводит большую часть денег новому получателю; банк ей не звонил. Похоже на схему «безопасный счёт». Проверить: связаться с клиенткой по номеру из профиля, запросить данные получателя через Антифрод-центр."}'

_pending: set[str] = set()
_lock = threading.Lock()


def _facts(st: State, tr: Transfer) -> list[str]:
    c = st.clients[tr.client_id]
    lines = [f"клиент: {c.age} лет, перевод {_fmt(tr.amount)}, статус: {tr.status}"]
    lines += [REASONS[r]["ru"].format(**tr.reason_kw) for r in tr.reasons if r in REASONS and r != "KNOWN_RECIPIENT"]
    if tr.answers is not None:
        lines.append("на контрольные вопросы ответил(а) «да»" if any(tr.answers) else "на контрольные вопросы ответил(а) «нет» (при звонке — возможно, подсказали)")
    fr = st.family.get(tr.family_request_id or "")
    if fr:
        lines.append({"pending": "ждёт решения доверенного лица", "declined": "доверенное лицо отклонило",
                      "approved": "доверенное лицо разрешило", "expired": "доверенное лицо не ответило за 15 минут",
                      "withdrawn": "запрос семье отозван"}.get(fr.status, ""))
    if tr.analysis:
        lines.append(f"вывод Qaqpan за час: {tr.analysis['verdict']}")
    d = drop_profile(st, tr.account)
    if d["label"] != "ok":
        lines.append("счёт получателя: " + ", ".join(d["signals"]))
    since = time.time() - 3 * 3600
    lines += [f"сегодня: {a.text['ru']}" for a in st.alerts.get(tr.client_id, []) if a.ts >= since][-5:]
    return [x for x in lines if x]


def _template(st: State, tr: Transfer) -> str:
    r = set(tr.reasons)
    alerts = " ".join(a.text["ru"] for a in st.alerts.get(tr.client_id, []))
    if "OWN_OTHER_BANK" in r:
        scheme = "первый шаг схемы «переведите на свою карту в другом банке»"
    elif ("CALL_ACTIVE" in r or "RECENT_CALL" in r) and "банк не звонит" in alerts:
        scheme = "схему «служба безопасности банка / безопасный счёт»: банк клиенту не звонил"
    elif "CALL_ACTIVE" in r or "RECENT_CALL" in r:
        scheme = "перевод под диктовку по телефону"
    elif tr.template == "purchase":
        scheme = "предоплату продавцу-мошеннику"
    else:
        scheme = "перевод под давлением"
    who = st.clients[tr.client_id]
    parts = [f"{who.short}, {who.age} лет: {_fmt(tr.amount)} → {st.accounts[tr.account].display}. Похоже на {scheme}."]
    d = drop_profile(st, tr.account)
    if d["label"] == "drop":
        parts.append("Счёт получателя похож на дроп: " + ", ".join(d["signals"]) + ".")
    parts.append("Проверить: связаться с клиентом по номеру из профиля; при подтверждении — передать счёт в Антифрод-центр.")
    return " ".join(parts)


def note(st: State, tr: Transfer) -> dict:
    """The rules summary at once; the AI version replaces it in the background when the model answers."""
    if tr.analyst_note is None:
        tr.analyst_note = {"text": _template(st, tr), "source": "rules"}
    if tr.analyst_note["source"] == "rules" and not tr.analyst_note.get("tried") and tr.id not in _pending:
        with _lock:
            _pending.add(tr.id)
        threading.Thread(target=_upgrade, args=(st, tr), daemon=True).start()
    return tr.analyst_note


def _upgrade(st: State, tr: Transfer) -> None:
    try:
        facts = _facts(st, tr)
        res, src = llm.cached_call("analyst", {"facts": facts}, AnalystNote,
                                   lambda: llm.parse(SYSTEM, "Факты:\n- " + "\n- ".join(facts), AnalystNote, EXAMPLE, max_tokens=300))
        if res and res.summary.strip():
            tr.analyst_note = {"text": res.summary.strip(), "source": "cache" if src == "cache" else "llm"}
    finally:
        if tr.analyst_note is not None:
            tr.analyst_note["tried"] = True  # one AI attempt per transfer, never a call on every poll
        with _lock:
            _pending.discard(tr.id)


# ---------------------------------------------------------------- console

def item(st: State, tr: Transfer) -> dict:
    c = st.clients[tr.client_id]
    acc = st.accounts[tr.account]
    typical = typical_spend(st, c.id)
    since = time.time() - 3 * 3600
    fr = st.family.get(tr.family_request_id or "")
    return {
        "id": tr.id, "ts": tr.ts, "status": tr.status, "score": tr.score, "amount": tr.amount,
        "client": {"id": c.id, "name": c.name, "age": c.age, "city": c.city},
        "recipient": {"display": acc.display, "holder": acc.holder, "bank": acc.bank},
        "reasons": [REASONS[r]["ru"].format(**tr.reason_kw) for r in tr.reasons if r in REASONS and r != "KNOWN_RECIPIENT"],
        "unusual_x": round(tr.amount / typical) if typical else None,
        "drop": drop_profile(st, tr.account),
        "family": fr.status if fr else None,
        "delay": tr.analysis["verdict"] if tr.analysis else None,
        "release_at": tr.release_at if tr.status == "delayed" else None,
        "timeline": [{"ts": a.ts, "text": a.text["ru"]} for a in st.alerts.get(c.id, []) if a.ts >= since],
        "note": note(st, tr),
        "decided_by_bank": tr.decided_by_bank,
    }


def console(st: State) -> dict:
    risky = [t for t in st.transfers.values() if t.level > 0 or t.status in ACTIVE]
    active = [t for t in risky if t.status in ACTIVE]
    done = [t for t in risky if t.status not in ACTIVE and t.status not in ("questions", "warning")]
    found = drops(st)
    return {
        "stats": {"saved": st.saved, "stopped": st.stopped, "queue": len(active),
                  "drops": sum(1 for d in found if d["label"] == "drop"), "checked": len(st.transfers)},
        "queue": [item(st, t) for t in sorted(active, key=lambda t: -t.ts)],
        "history": [item(st, t) for t in sorted(done, key=lambda t: -t.ts)[:8]],
        "drops": found,
    }
