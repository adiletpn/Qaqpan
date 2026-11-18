"""Qalqan API: one process, in-memory state, serves the built web app (web/dist).

Layers (docs/DEMO_SCENARIO.md):
  1 «Написали»     POST /api/messages/check
  2 «Позвонили»    POST /api/calls/verify
  3 «Уговорили»    POST /api/transfers (+ /answers, /cancel, /proceed), family shield
  4 «Получили»     POST /api/complaints -> every later transfer to that account is held
  + help           POST /api/victim/help, GET /api/schemes
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import llm, msgcheck, schemes, victim
from .risk import assess
from .schemas import (AnswersRequest, CallVerifyRequest, CallVerifyResult, CheckResult, ComplaintRequest,
                      ComplaintResult, FamilyDecision, MessageCheckRequest, NativeCallSignal, Question, TransferRequest, TransferView,
                      VictimHelp, VictimRequest)
from .state import BANK_NUMBER, FAMILY_TIMEOUT_S, SCAM_NUMBER, STATE, Call, FamilyRequest, Sms, Transfer
from .texts import QUESTIONS, reason_text, t

logging.basicConfig(level=logging.INFO)
ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = ROOT / "web" / "dist"

app = FastAPI(title="Qalqan API", version="1.0.0")

FLAGGED = ("RECIPIENT_COMPLAINTS", "RECIPIENT_AFC")


def _client(cid: str):
    c = STATE.clients.get(cid)
    if not c:
        raise HTTPException(404, f"unknown client {cid}")
    return c


def _transfer(tid: str) -> Transfer:
    tr = STATE.transfers.get(tid)
    if not tr:
        raise HTTPException(404, f"unknown transfer {tid}")
    return tr


def _fmt(amount: float) -> str:
    return f"{amount:,.0f} ₸".replace(",", " ")


def _view(tr: Transfer) -> TransferView:
    c = STATE.clients[tr.client_id]
    lang = c.lang
    acc = STATE.accounts[tr.account]
    title = message = None
    questions: list[Question] = []
    guardian = STATE.clients[c.guardian_id].short if c.guardian_id else None
    flagged = any(r in FLAGGED for r in tr.reasons)
    said_yes = bool(tr.answers and any(tr.answers))
    if tr.status == "completed":
        title = t("done.title", lang)
        fr = STATE.family.get(tr.family_request_id or "")
        if fr and fr.status == "approved":
            message = t("family.approved", lang, name=guardian)
    elif tr.status == "warning":
        title, message = t("warn.title", lang), t("warn.new_recipient", lang)
    elif tr.status == "questions":
        title = t("hold.title", lang)
        message = t("hold.complaints" if flagged else "hold.call" if tr.template == "call" else "hold.generic", lang)
        questions = [Question(id=i, text=q[lang]) for i, q in enumerate(QUESTIONS[tr.template])]
    elif tr.status == "awaiting_family":
        title = t("scam.title", lang) if said_yes else t("hold.title", lang)
        parts = [t("scam.call", lang)] if said_yes else []
        parts.append(t("family.sent", lang, name=guardian))
        message = " ".join(parts)
    elif tr.status in ("held", "escalated"):
        title = t("scam.title", lang) if said_yes or flagged else t("hold.title", lang)
        if said_yes:
            base = t("scam.purchase" if tr.template == "purchase" else "scam.call", lang)
        else:
            base = t("flagged", lang) if flagged else ""
        message = (base + " " + t("bank.callback", lang)).strip()
    elif tr.status == "cancelled":
        title = t("safe.money", lang)
        fr = STATE.family.get(tr.family_request_id or "")
        message = t("family.declined", lang, name=guardian) if fr and fr.status == "declined" else t("cancel.title", lang)
    return TransferView(
        id=tr.id, status=tr.status, level=tr.level, score=tr.score, amount=tr.amount, account=acc.display,
        holder=acc.holder, title=title, message=message, questions=questions,
        reasons=[reason_text(r, lang, **tr.reason_kw) for r in tr.reasons if r != "KNOWN_RECIPIENT"],
        guardian_name=guardian, balance=c.balance,
    )


def _step_for(tr: Transfer) -> str:
    return "received" if any(r in FLAGGED for r in tr.reasons) else "persuaded"


# ---------------------------------------------------------------------------- meta

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "llm": llm.status()}


@app.get("/api/clients")
def clients() -> list[dict]:
    return [{"id": c.id, "name": c.name, "short": c.short, "lang": c.lang, "avatar": c.avatar} for c in STATE.clients.values()]


@app.get("/api/samples")
def samples() -> list[dict]:
    return list(msgcheck.load_samples().values())


@app.get("/api/schemes")
def get_schemes(lang: str = "ru") -> list[dict]:
    return schemes.cards("kk" if lang == "kk" else "ru")


# ---------------------------------------------------------------------------- phone snapshot

@app.get("/api/phone/{cid}")
def phone(cid: str) -> dict:
    c = _client(cid)
    with STATE.lock:
        STATE.expire_family()
        call = STATE.calls.get(cid)
        pending = []
        for fr in STATE.family.values():
            if fr.guardian_id == cid and fr.status == "pending":
                tr = STATE.transfers[fr.transfer_id]
                frm = STATE.clients[fr.from_client]
                pending.append({
                    "id": fr.id, "from_name": frm.short, "amount": tr.amount,
                    "account": STATE.accounts[tr.account].display, "holder": STATE.accounts[tr.account].holder,
                    "reasons": [reason_text(r, c.lang, **tr.reason_kw) for r in tr.reasons if r != "KNOWN_RECIPIENT"],
                    "said_yes": bool(tr.answers and any(tr.answers)),
                    "expires_in": max(0, int(fr.expires - time.time())),
                })
        return {
            "client": {"id": c.id, "name": c.name, "short": c.short, "lang": c.lang, "balance": c.balance,
                       "avatar": c.avatar, "guardian": STATE.clients[c.guardian_id].short if c.guardian_id else None},
            "call": None if not call else {"number": call.number, "label": call.caller_label, "answered": call.answered,
                                           "since": call.started},
            "sms": [{"id": s.id, "sender": s.sender, "text": s.text, "sample_id": s.sample_id, "ts": s.ts} for s in STATE.sms[cid]],
            "prefill": STATE.prefill[cid],
            "nav": STATE.nav[cid],
            "transfers": [_view(tr).model_dump() for tr in list(STATE.transfers.values())[-5:] if tr.client_id == cid],
            "family_requests": pending,
        }


@app.post("/api/phone/{cid}/lang/{lang}")
def set_lang(cid: str, lang: str) -> dict:
    _client(cid).lang = "kk" if lang == "kk" else "ru"
    return {"lang": _client(cid).lang}


@app.post("/api/phone/{cid}/call/answer")
def answer_call(cid: str) -> dict:
    with STATE.lock:
        call = STATE.calls.get(cid)
        if not call:
            raise HTTPException(409, "no incoming call")
        call.answered = True
        STATE.emit("call", cid, f"{_client(cid).short} ответил(а) на звонок {call.number}")
    return {"ok": True}


@app.post("/api/phone/{cid}/call/end")
def end_call(cid: str) -> dict:
    with STATE.lock:
        call = STATE.calls.pop(cid, None)
        if call:
            STATE.last_call_number[cid] = call.number
            STATE.bank_outbound.pop(cid, None)
    return {"ok": True}


NATIVE_NUMBER = "native"


@app.post("/api/phone/{cid}/native-call")
def native_call(cid: str, req: NativeCallSignal) -> dict:
    """Real call signal from the Android/iOS wrapper. Never carries the number or the audio."""
    _client(cid)
    with STATE.lock:
        call = STATE.calls.get(cid)
        if req.on_call and call is None:
            STATE.calls[cid] = Call(NATIVE_NUMBER, "Телефонный звонок", time.time(), answered=True)
            STATE.emit("call", cid, f"{_client(cid).short}: системный сигнал — идёт звонок")
        elif not req.on_call and call is not None and call.number == NATIVE_NUMBER:
            STATE.calls.pop(cid)
    return {"on_call": req.on_call}


# ---------------------------------------------------------------------------- layer 1: messages

@app.post("/api/messages/check", response_model=CheckResult)
def check_message(req: MessageCheckRequest) -> CheckResult:
    try:
        res = msgcheck.check(req.text, req.image_b64, req.media_type, req.sample_id, req.lang)
    except ValueError:
        raise HTTPException(422, "Нужен текст, ссылка или скриншот")
    who = STATE.clients[req.client_id].short if req.client_id in STATE.clients else "Клиент"
    if res.verdict == "scam":
        STATE.emit("message", req.client_id, f"{who}: сообщение — мошенничество ({res.scheme_name or 'схема'})",
                   step="written", stopped=True)
    else:
        STATE.emit("message", req.client_id, f"{who}: проверено сообщение — {res.verdict}")
    return res


# ---------------------------------------------------------------------------- layer 2: calls

@app.post("/api/calls/verify", response_model=CallVerifyResult)
def verify_call(req: CallVerifyRequest) -> CallVerifyResult:
    c = _client(req.client_id)
    lang = req.lang or c.lang
    with STATE.lock:
        call = STATE.calls.get(c.id)
        if not call or not call.answered:
            return CallVerifyResult(status="no_call", title=t("call.none.title", lang), message=t("call.none.msg", lang))
        outbound = STATE.bank_outbound.get(c.id)  # the bank's own call log is the source of truth
        if outbound:
            return CallVerifyResult(status="bank", title=t("call.yes.title", lang), number=call.number,
                                    message=t("call.yes.msg", lang, employee=outbound.employee, department=outbound.department))
        n = STATE.number_complaints.get(call.number, 0)
        msg = t("call.no.msg", lang) + (" " + t("call.no.complaints", lang, n=n) if n else "")
        STATE.emit("call_verify", c.id, f"{c.short}: «банк» не звонит — звонок с {call.number} мошеннический",
                   step="called", stopped=True)
        return CallVerifyResult(status="not_bank", title=t("call.no.title", lang), message=msg,
                                number=call.number, number_complaints=n)


# ---------------------------------------------------------------------------- layer 3: transfers

@app.post("/api/transfers", response_model=TransferView)
def create_transfer(req: TransferRequest) -> TransferView:
    c = _client(req.client_id)
    with STATE.lock:
        if req.amount > c.balance:
            raise HTTPException(422, "Недостаточно средств")
        acc = STATE.account(req.account)
        call = STATE.calls.get(c.id)
        on_call = bool(call and call.answered and c.id not in STATE.bank_outbound)
        a = assess(c, acc, req.amount, on_call, req.context.pasted, req.context.app_switches)
        tr = Transfer(STATE.new_id("TR"), c.id, acc.number, req.amount, time.time(), a.score, a.level,
                      a.reasons, a.kw, a.template, status="completed")
        if a.level == 0:
            c.balance -= req.amount
            c.known_accounts.add(acc.number)
        elif a.level == 1:
            tr.status = "warning"
        else:
            tr.status = "questions"
        STATE.transfers[tr.id] = tr
        STATE.prefill[c.id] = None
        why = ", ".join(reason_text(r, "ru", **a.kw) for r in a.reasons if r != "KNOWN_RECIPIENT")
        flagged = a.level >= 2 and any(r in FLAGGED for r in a.reasons)
        STATE.emit("transfer", c.id, f"{c.short}: перевод {_fmt(req.amount)} → {acc.holder} · риск {a.score:.2f}"
                   + (f" ({why})" if why else ""), step="received" if flagged else None)
        return _view(tr)


@app.post("/api/transfers/{tid}/answers", response_model=TransferView)
def answer_questions(tid: str, req: AnswersRequest) -> TransferView:
    with STATE.lock:
        tr = _transfer(tid)
        if tr.status != "questions":
            raise HTTPException(409, f"transfer is {tr.status}")
        c = STATE.clients[tr.client_id]
        tr.answers = req.answers
        said_yes = any(req.answers)
        flagged = any(r in FLAGGED for r in tr.reasons)
        if said_yes:
            tr.level = 3
            tr.reasons.append("SAID_YES")
        if c.guardian_id and tr.amount >= c.family_limit:
            # family shield: works even if the scammer coached the victim to answer «no»
            fr = FamilyRequest(STATE.new_id("FR"), tr.id, c.id, c.guardian_id, time.time(), time.time() + FAMILY_TIMEOUT_S)
            STATE.family[fr.id] = fr
            tr.family_request_id = fr.id
            tr.status = "awaiting_family"
            g = STATE.clients[c.guardian_id].short
            STATE.emit("family", c.id, f"Семейный щит: запрос {g} — подтвердить перевод {_fmt(tr.amount)}?")
        elif said_yes or flagged:
            tr.status = "held"
            STATE.emit("held", c.id, f"{c.short}: перевод {_fmt(tr.amount)} остановлен, банк перезвонит",
                       step=_step_for(tr), stopped=True)
        else:
            tr.status = "warning"
        return _view(tr)


@app.post("/api/transfers/{tid}/cancel", response_model=TransferView)
def cancel_transfer(tid: str) -> TransferView:
    with STATE.lock:
        tr = _transfer(tid)
        if tr.status in ("completed", "cancelled"):
            raise HTTPException(409, f"transfer is {tr.status}")
        prev = tr.status
        tr.status = "cancelled"
        c = STATE.clients[tr.client_id]
        if prev != "warning" or tr.level >= 1:
            STATE.emit("cancel", c.id, f"{c.short}: отменил(а) перевод {_fmt(tr.amount)} после предупреждения Qalqan",
                       step=_step_for(tr), stopped=True)
        return _view(tr)


@app.post("/api/transfers/{tid}/proceed", response_model=TransferView)
def proceed_transfer(tid: str) -> TransferView:
    with STATE.lock:
        tr = _transfer(tid)
        if tr.status != "warning":
            raise HTTPException(409, f"transfer is {tr.status}")
        c = STATE.clients[tr.client_id]
        if tr.amount > c.balance:
            raise HTTPException(422, "Недостаточно средств")
        c.balance -= tr.amount
        tr.status = "completed"
        STATE.emit("transfer_done", c.id, f"{c.short}: перевод {_fmt(tr.amount)} выполнен после предупреждения")
        return _view(tr)


@app.post("/api/family/{rid}/decision")
def family_decision(rid: str, req: FamilyDecision) -> dict:
    with STATE.lock:
        fr = STATE.family.get(rid)
        if not fr or fr.status != "pending":
            raise HTTPException(409, "request is not pending")
        tr = STATE.transfers[fr.transfer_id]
        c = STATE.clients[fr.from_client]
        g = STATE.clients[fr.guardian_id]
        if req.approve:
            fr.status = "approved"
            if tr.amount <= c.balance:
                c.balance -= tr.amount
                tr.status = "completed"
            STATE.emit("family_ok", c.id, f"{g.short} подтвердил(а) перевод {_fmt(tr.amount)}")
        else:
            fr.status = "declined"
            tr.status = "cancelled"
            STATE.emit("family_no", c.id, f"{g.short} отклонил(а) перевод {_fmt(tr.amount)} — деньги {c.short} спасены",
                       step="persuaded", stopped=True)
        return {"status": fr.status, "transfer": _view(tr).model_dump()}


# ---------------------------------------------------------------------------- layer 4: complaints

@app.post("/api/complaints", response_model=ComplaintResult)
def complain(req: ComplaintRequest) -> ComplaintResult:
    c = _client(req.client_id)
    with STATE.lock:
        if req.transfer_id:
            acc = STATE.accounts[_transfer(req.transfer_id).account]
        elif req.account:
            acc = STATE.account(req.account)
        else:
            raise HTTPException(422, "Нужен перевод или номер счёта")
        acc.complaints += 1
        number = (STATE.calls.get(c.id).number if STATE.calls.get(c.id) else STATE.last_call_number.get(c.id))
        if number and number != BANK_NUMBER:
            STATE.number_complaints[number] = STATE.number_complaints.get(number, 0) + 1
        STATE.emit("complaint", c.id, f"Жалоба {c.short}: счёт {acc.display} помечен — "
                   "все клиенты, кто попробует туда перевести, получат предупреждение")
        return ComplaintResult(message=t("complaint.done", c.lang), account_complaints=acc.complaints, number_flagged=number)


# ---------------------------------------------------------------------------- help

@app.post("/api/victim/help", response_model=VictimHelp)
def victim_help(req: VictimRequest) -> VictimHelp:
    c = _client(req.client_id)
    lang = req.lang or c.lang
    amount = account = None
    if req.transfer_id and req.transfer_id in STATE.transfers:
        tr = STATE.transfers[req.transfer_id]
        amount, account = tr.amount, STATE.accounts[tr.account].display
    phone_no = STATE.last_call_number.get(c.id) or (STATE.calls[c.id].number if c.id in STATE.calls else None)
    scheme = "полиции / банка" if lang == "ru" else "полиция / банк"
    return victim.build(lang, c.name, amount, account, phone_no, scheme, req.story)


# ---------------------------------------------------------------------------- stage & director

@app.get("/api/stage")
def stage(since: int = 0) -> dict:
    with STATE.lock:
        return {
            "steps": sorted(STATE.steps),
            "stopped": STATE.stopped,
            "events": [{"seq": e.seq, "ts": e.ts, "kind": e.kind, "client_id": e.client_id, "text": e.text,
                        "step": e.step, "stopped": e.stopped} for e in STATE.events if e.seq > since][-30:],
        }


DEMO_ACCOUNT = "KZ86 8562 0000 0471 1934"


@app.post("/api/director/{action}")
def director(action: str) -> dict:
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
            end_call("aigerim")
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
            raise HTTPException(404, f"unknown action {action}")
    return {"ok": True, "action": action}


@app.post("/api/demo/reset")
def reset() -> dict:
    STATE.reset()
    return {"ok": True}


# ---------------------------------------------------------------------------- static web app

if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")
    if (WEB_DIST / "samples").exists():
        app.mount("/samples", StaticFiles(directory=WEB_DIST / "samples"), name="samples")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        f = WEB_DIST / path
        if path and f.is_file() and WEB_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(WEB_DIST / "index.html")
