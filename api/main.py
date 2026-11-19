"""Qaqpan API: one process, in-memory state, serves the built web app (web/dist).

Layers (docs/DEMO_SCENARIO.md):
  1 «Написали»     POST /api/messages/check
  2 «Позвонили»    POST /api/calls/verify
  3 «Уговорили»    POST /api/transfers (+ /answers, /cancel, /proceed), family shield (/api/family/...)
  4 «Получили»     POST /api/complaints -> every later transfer to that account is held
  + help           POST /api/victim/help, GET /api/schemes
"""

from __future__ import annotations

import hmac
import logging
import os
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import director, family, llm, msgcheck, schemes, victim
from .risk import assess
from .schemas import (AnswersRequest, CallVerifyRequest, CallVerifyResult, CheckResult, ComplaintRequest,
                      ComplaintResult, FamilyDecision, MessageCheckRequest, NativeCallSignal, Question,
                      TransferRequest, TransferView, VictimHelp, VictimRequest)
from .state import (BANK_NUMBER, FAMILY_TIMEOUT_S, NATIVE_NUMBER, STATE, Call, FamilyRequest, Transfer, digits)
from .texts import QUESTIONS, reason_text, t

logging.basicConfig(level=logging.INFO)
ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = ROOT / "web" / "dist"

app = FastAPI(title="Qaqpan API", version="1.1.0")

FLAGGED = ("RECIPIENT_COMPLAINTS", "RECIPIENT_AFC")
DUPLICATE_WINDOW_S = 5


def require_director(x_director_key: str | None = Header(default=None)) -> None:
    """On a public link set QAQPAN_DIRECTOR_KEY so that only the presenter can drive or reset the demo."""
    key = os.getenv("QAQPAN_DIRECTOR_KEY")
    if key and not hmac.compare_digest(x_director_key or "", key):
        raise HTTPException(403, "Нужен ключ ведущего")


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


def _guardian_name(cid: str) -> str | None:
    link = STATE.link_for_ward(cid)
    return STATE.clients[link.guardian_id].short if link else None


def _view(tr: Transfer) -> TransferView:
    c = STATE.clients[tr.client_id]
    lang = c.lang
    acc = STATE.accounts[tr.account]
    title = message = None
    questions: list[Question] = []
    fr = STATE.family.get(tr.family_request_id or "")
    guardian = STATE.clients[fr.guardian_id].short if fr else _guardian_name(c.id)
    flagged = any(r in FLAGGED for r in tr.reasons)
    said_yes = bool(tr.answers and any(tr.answers))
    if tr.status == "completed":
        title = t("done.title", lang)
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
        if fr and fr.status == "declined":
            message = t("family.declined", lang, name=guardian)
        elif tr.note == "insufficient":
            message = t("cancel.insufficient", lang)
        else:
            message = t("cancel.title", lang)
    return TransferView(
        id=tr.id, status=tr.status, level=tr.level, score=tr.score, amount=tr.amount, account=acc.display,
        holder=acc.holder, title=title, message=message, questions=questions,
        reasons=[reason_text(r, lang, **tr.reason_kw) for r in tr.reasons if r != "KNOWN_RECIPIENT"],
        guardian_name=guardian, balance=c.balance,
    )


def _step_for(tr: Transfer) -> str:
    return "received" if any(r in FLAGGED for r in tr.reasons) else "persuaded"


def _withdraw_family(tr: Transfer) -> None:
    fr = STATE.family.get(tr.family_request_id or "")
    if fr and fr.status == "pending":
        fr.status = "withdrawn"
    for n in STATE.notices.get(fr.guardian_id, []) if fr else []:
        if n.ref == fr.id:
            n.seen = True


# ---------------------------------------------------------------------------- meta

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": app.version, "llm": llm.status(),
            "director_protected": bool(os.getenv("QAQPAN_DIRECTOR_KEY"))}


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
        requests = [family.request_view(fr, c.lang) for fr in STATE.family.values()
                    if fr.guardian_id == cid and fr.status == "pending"]
        mine = [tr for tr in STATE.transfers.values() if tr.client_id == cid][-5:]
        return {
            "epoch": STATE.epoch,
            "client": {"id": c.id, "name": c.name, "short": c.short, "lang": c.lang, "balance": c.balance,
                       "avatar": c.avatar, "guardian": _guardian_name(cid), "phone": c.phone},
            "call": None if not call else {"number": call.number, "label": call.caller_label, "answered": call.answered,
                                           "since": call.started},
            "sms": [{"id": s.id, "sender": s.sender, "text": s.text, "sample_id": s.sample_id, "ts": s.ts} for s in STATE.sms[cid]],
            "prefill": STATE.prefill[cid],
            "nav": STATE.nav[cid],
            "transfers": [_view(tr).model_dump() for tr in mine],
            "family_requests": requests,
            "notices": [{"id": n.id, "ts": n.ts, "kind": n.kind, "title": n.title[c.lang], "body": n.body[c.lang],
                         "ref": n.ref} for n in STATE.notices[cid] if not n.seen][-3:],
            "shield": family.shield_info(cid, c.lang),
        }


@app.post("/api/phone/{cid}/lang/{lang}")
def set_lang(cid: str, lang: str) -> dict:
    _client(cid).lang = "kk" if lang == "kk" else "ru"
    return {"lang": _client(cid).lang}


@app.post("/api/phone/{cid}/notices/{nid}/seen")
def notice_seen(cid: str, nid: str) -> dict:
    _client(cid)
    with STATE.lock:
        for n in STATE.notices[cid]:
            if n.id == nid:
                n.seen = True
    return {"ok": True}


@app.post("/api/phone/{cid}/call/answer")
def answer_call(cid: str) -> dict:
    c = _client(cid)
    with STATE.lock:
        call = STATE.calls.get(cid)
        if not call:
            raise HTTPException(409, "Нет входящего звонка")
        if not call.answered:
            call.answered = True
            STATE.alert(cid, "Начался телефонный звонок", "Телефон қоңырауы басталды")
            STATE.emit("call", cid, f"{c.short} ответил(а) на звонок {call.number}")
    return {"ok": True}


@app.post("/api/phone/{cid}/call/end")
def end_call(cid: str) -> dict:
    _client(cid)
    STATE.end_call(cid)
    return {"ok": True}


@app.post("/api/phone/{cid}/native-call")
def native_call(cid: str, req: NativeCallSignal) -> dict:
    """Real call signal from the Android/iOS wrapper. Never carries the number or the audio."""
    c = _client(cid)
    with STATE.lock:
        call = STATE.calls.get(cid)
        if req.on_call and call is None:
            STATE.calls[cid] = Call(NATIVE_NUMBER, "Телефонный звонок", time.time(), answered=True)
            STATE.alert(cid, "Начался телефонный звонок", "Телефон қоңырауы басталды")
            STATE.emit("call", cid, f"{c.short}: системный сигнал — идёт звонок")
        elif not req.on_call and call is not None and call.number == NATIVE_NUMBER:
            STATE.end_call(cid)
    return {"on_call": req.on_call}


# ---------------------------------------------------------------------------- layer 1: messages

@app.post("/api/messages/check", response_model=CheckResult)
def check_message(req: MessageCheckRequest) -> CheckResult:
    try:
        res = msgcheck.check(req.text, req.image_b64, req.media_type, req.sample_id, req.lang)
    except ValueError:
        raise HTTPException(422, "Нужен текст, ссылка или скриншот")
    cid = req.client_id if req.client_id in STATE.clients else None
    who = STATE.clients[cid].short if cid else "Клиент"
    if res.verdict == "scam":
        names = msgcheck.SCHEME_NAME.get(res.scheme or "", {"ru": "схема", "kk": "схема"})
        STATE.alert(cid, f"Проверено сообщение — мошенничество ({names['ru']})",
                    f"Хабарлама тексерілді — алаяқтық ({names['kk']})")
        STATE.emit("message", cid, f"{who}: сообщение — мошенничество ({res.scheme_name or 'схема'})",
                   step="written", stopped=True)
    else:
        STATE.emit("message", cid, f"{who}: проверено сообщение — {res.verdict}")
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
        outbound = STATE.bank_outbound.get(c.id)  # the bank's own call log is the source of truth, not caller ID
        if outbound:
            return CallVerifyResult(status="bank", title=t("call.yes.title", lang), number=call.number,
                                    message=t("call.yes.msg", lang, employee=outbound.employee, department=outbound.department))
        known_number = call.number != NATIVE_NUMBER
        n = STATE.number_complaints.get(call.number, 0) if known_number else 0
        msg = t("call.no.msg", lang) + (" " + t("call.no.complaints", lang, n=n) if n else "")
        STATE.alert(c.id, "Проверка звонка: банк не звонит", "Қоңырауды тексеру: банк қоңырау шалмайды")
        STATE.emit("call_verify", c.id, f"{c.short}: банк не звонит — собеседник, назвавшийся банком, мошенник",
                   step="called", stopped=True)
        return CallVerifyResult(status="not_bank", title=t("call.no.title", lang), message=msg,
                                number=call.number if known_number else None, number_complaints=n)


# ---------------------------------------------------------------------------- layer 3: transfers

@app.post("/api/transfers", response_model=TransferView)
def create_transfer(req: TransferRequest) -> TransferView:
    c = _client(req.client_id)
    num = digits(req.account)
    if not 12 <= len(num) <= 20:
        raise HTTPException(422, "Проверьте номер счёта или карты")
    with STATE.lock:
        now = time.time()
        for tr in reversed(list(STATE.transfers.values())):  # double tap on «Перевести» must not send twice
            if now - tr.ts > DUPLICATE_WINDOW_S:
                break
            if tr.client_id == c.id and tr.account == num and tr.amount == req.amount and tr.status != "cancelled":
                return _view(tr)
        if req.amount > c.balance:
            raise HTTPException(422, "Недостаточно средств")
        acc = STATE.account(req.account)
        call = STATE.calls.get(c.id)
        on_call = bool(call and call.answered and c.id not in STATE.bank_outbound)
        a = assess(c, acc, req.amount, on_call, req.context.pasted, req.context.app_switches)
        tr = Transfer(STATE.new_id("TR"), c.id, acc.number, req.amount, now, a.score, a.level,
                      a.reasons, a.kw, a.template, status="completed")
        if a.level == 0:
            c.balance -= req.amount
            c.known_accounts.add(acc.number)
        else:
            tr.status = "warning" if a.level == 1 else "questions"
            STATE.alert(c.id, f"Перевод {_fmt(req.amount)} — Qaqpan поставил на паузу",
                        f"{_fmt(req.amount)} аударым — Qaqpan тоқтатты")
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
            raise HTTPException(409, f"Перевод уже в статусе {tr.status}")
        c = STATE.clients[tr.client_id]
        tr.answers = req.answers
        said_yes = any(req.answers)
        flagged = any(r in FLAGGED for r in tr.reasons)
        if said_yes:
            tr.level = 3
            tr.reasons.append("SAID_YES")
        link = STATE.link_for_ward(c.id)
        if link and tr.amount >= link.limit:
            # family shield: works even if the scammer coached the victim to answer «no»
            now = time.time()
            fr = FamilyRequest(STATE.new_id("FR"), tr.id, c.id, link.guardian_id, now, now + FAMILY_TIMEOUT_S)
            STATE.family[fr.id] = fr
            tr.family_request_id = fr.id
            tr.status = "awaiting_family"
            family.notify_request(fr)
            g = STATE.clients[link.guardian_id].short
            STATE.emit("family", c.id, f"Семейный щит: {g} получил(а) уведомление — перевод {_fmt(tr.amount)} ждёт решения")
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
            raise HTTPException(409, f"Перевод уже в статусе {tr.status}")
        tr.status = "cancelled"
        _withdraw_family(tr)
        c = STATE.clients[tr.client_id]
        STATE.emit("cancel", c.id, f"{c.short}: отменил(а) перевод {_fmt(tr.amount)} после предупреждения Qaqpan",
                   step=_step_for(tr), stopped=True)
        return _view(tr)


@app.post("/api/transfers/{tid}/proceed", response_model=TransferView)
def proceed_transfer(tid: str) -> TransferView:
    with STATE.lock:
        tr = _transfer(tid)
        if tr.status != "warning":
            raise HTTPException(409, f"Перевод уже в статусе {tr.status}")
        c = STATE.clients[tr.client_id]
        if tr.amount > c.balance:
            raise HTTPException(422, "Недостаточно средств")
        c.balance -= tr.amount
        tr.status = "completed"
        STATE.emit("transfer_done", c.id, f"{c.short}: перевод {_fmt(tr.amount)} выполнен после предупреждения")
        return _view(tr)


# ---------------------------------------------------------------------------- family shield

@app.post("/api/family/requests/{rid}/decision")
def family_decision(rid: str, req: FamilyDecision) -> dict:
    with STATE.lock:
        STATE.expire_family()
        fr = STATE.family.get(rid)
        if not fr:
            raise HTTPException(404, "Запрос не найден")
        if fr.status != "pending":
            raise HTTPException(409, "Запрос уже закрыт")
        tr = STATE.transfers[fr.transfer_id]
        c = STATE.clients[fr.from_client]
        g = STATE.clients[fr.guardian_id]
        for n in STATE.notices[fr.guardian_id]:
            if n.ref == fr.id:
                n.seen = True
        if req.approve:
            fr.status = "approved"
            if tr.amount <= c.balance:
                c.balance -= tr.amount
                tr.status = "completed"
                STATE.emit("family_ok", c.id, f"{g.short} подтвердил(а) перевод {_fmt(tr.amount)}")
            else:
                tr.status, tr.note = "cancelled", "insufficient"
                STATE.emit("family_ok", c.id, f"{g.short} подтвердил(а), но средств уже не хватает — перевод отменён")
        else:
            fr.status = "declined"
            tr.status = "cancelled"
            STATE.alert(c.id, f"{g.short} отклонил(а) перевод", f"{g.short} аударымды қабылдамады")
            STATE.emit("family_no", c.id, f"{g.short} отклонил(а) перевод {_fmt(tr.amount)} — деньги {c.short} спасены",
                       step="persuaded", stopped=True)
        return {"status": fr.status, "transfer": _view(tr).model_dump()}


@app.post("/api/family/{ward_id}/disable")
def shield_disable(ward_id: str) -> dict:
    _client(ward_id)
    with STATE.lock:
        if ward_id not in STATE.links:
            raise HTTPException(404, "Семейный щит не подключён")
        link = family.request_disable(ward_id)
        return {"disable_at": link.disable_at}


@app.post("/api/family/{ward_id}/keep")
def shield_keep(ward_id: str) -> dict:
    _client(ward_id)
    with STATE.lock:
        if ward_id not in STATE.links:
            raise HTTPException(404, "Семейный щит не подключён")
        family.keep(ward_id)
        return {"disable_at": None}


# ---------------------------------------------------------------------------- layer 4: complaints

@app.post("/api/complaints", response_model=ComplaintResult)
def complain(req: ComplaintRequest) -> ComplaintResult:
    c = _client(req.client_id)
    with STATE.lock:
        if req.transfer_id:
            acc = STATE.accounts[_transfer(req.transfer_id).account]
        elif req.account and 12 <= len(digits(req.account)) <= 20:
            acc = STATE.account(req.account)
        else:
            raise HTTPException(422, "Нужен перевод или номер счёта")
        key = (c.id, acc.number)
        first = key not in STATE.complaints_by  # one client = one complaint per account
        call = STATE.calls.get(c.id)
        number = call.number if call else STATE.last_call_number.get(c.id)
        if number in (BANK_NUMBER, NATIVE_NUMBER):
            number = None
        if first:
            STATE.complaints_by.add(key)
            acc.complaints += 1
            if number:
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
        if tr.client_id == c.id:
            amount, account = tr.amount, STATE.accounts[tr.account].display
    call = STATE.calls.get(c.id)
    phone_no = STATE.last_call_number.get(c.id) or (call.number if call and call.number != NATIVE_NUMBER else None)
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


@app.post("/api/director/{action}", dependencies=[Depends(require_director)])
def director_action(action: str) -> dict:
    try:
        director.run(action)
    except KeyError:
        raise HTTPException(404, f"unknown action {action}")
    return {"ok": True, "action": action}


@app.post("/api/demo/reset", dependencies=[Depends(require_director)])
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
        if path.startswith("api/"):
            raise HTTPException(404, "Not Found")
        f = WEB_DIST / path
        if path and f.is_file() and WEB_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(WEB_DIST / "index.html")
