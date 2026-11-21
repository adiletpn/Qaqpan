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

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import assistant, delay, director, family, llm, msgcheck, schemes, victim
from .risk import assess
from .schemas import (AnswersRequest, AssistantRequest, CallVerifyRequest, CallVerifyResult, CheckResult, CodewordRequest,
                      ComplaintRequest, ComplaintResult, FamilyDecision, MessageCheckRequest, NativeCallSignal, Question,
                      RecipientCheck, TransferRequest, TransferView, VictimHelp, VictimRequest)
from .state import (BANK_NUMBER, DELAY_S, FAMILY_TIMEOUT_S, NATIVE_NUMBER, SANDBOX_ID, STATE, Call, Client, FamilyLink,
                    FamilyRequest, State, Transfer, current, digits, in_sandbox, sandbox, use_state)
from .texts import QUESTIONS, reason_text, t

logging.basicConfig(level=logging.INFO)
ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = ROOT / "web" / "dist"

app = FastAPI(title="Qaqpan API", version="1.2.0")


class SandboxMiddleware:
    """X-Qaqpan-Session: <id> routes the request to that visitor's own demo world (self-guided tour on /try)."""

    def __init__(self, app_):
        self.app = app_

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        sid = dict(scope.get("headers") or []).get(b"x-qaqpan-session", b"").decode("latin-1")
        token = use_state(sandbox(sid) if SANDBOX_ID.fullmatch(sid) else None)
        try:
            await self.app(scope, receive, send)
        finally:
            from .state import _current
            _current.reset(token)


app.add_middleware(SandboxMiddleware)

FLAGGED = ("RECIPIENT_COMPLAINTS", "RECIPIENT_AFC")


def SHADOW() -> bool:  # noqa: N802 — read per request so tests can flip it
    """Pilot mode QAQPAN_SHADOW=1: Qaqpan scores and logs every transfer but never delays the money."""
    return os.getenv("QAQPAN_SHADOW") == "1"
DUPLICATE_WINDOW_S = 5
NAV_TTL_MS = 15_000


LOCK_OPEN = ("/api/messages/check",)  # «попробуйте сами»: anyone may check a message even on a locked stand


@app.middleware("http")
async def lock_stand(request: Request, call_next):
    """QAQPAN_LOCK=1 (a private stand for the final): every action needs the presenter key, so nobody with the link
    can interfere with the live demo. The phones remember the key from ?key=… like the stage does."""
    key = os.getenv("QAQPAN_DIRECTOR_KEY")
    if (os.getenv("QAQPAN_LOCK") == "1" and key and not in_sandbox() and request.method == "POST"
            and request.url.path.startswith("/api/")
            and request.url.path not in LOCK_OPEN
            and not hmac.compare_digest(request.headers.get("x-director-key", ""), key)):
        return JSONResponse({"detail": "Закрытый стенд: нужен ключ ведущего"}, status_code=403)
    return await call_next(request)


def _idle_reset() -> None:
    """QAQPAN_IDLE_RESET_MIN=10 on the public link: after 10 quiet minutes the next visitor sees a clean demo,
    not someone else's test transfers."""
    minutes = float(os.getenv("QAQPAN_IDLE_RESET_MIN", "0") or 0)
    with STATE.lock:
        if minutes and len(STATE.events) > 1 and time.time() - STATE.events[-1].ts > minutes * 60:
            STATE.reset()


def require_director(x_director_key: str | None = Header(default=None)) -> None:
    """On a public link set QAQPAN_DIRECTOR_KEY so that only the presenter can drive or reset the demo."""
    key = os.getenv("QAQPAN_DIRECTOR_KEY")
    if key and not in_sandbox() and not hmac.compare_digest(x_director_key or "", key):  # a sandbox drives only itself
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
    elif tr.status == "delayed":
        title, message = t("delay.title", lang), t("delay.msg", lang)
    elif tr.status == "held" and tr.note == "delay_scam":
        title, message = t("scam.title", lang), t("delay.held", lang) + " " + t("bank.callback", lang)
    elif tr.status in ("held", "escalated"):
        title = t("scam.title", lang) if said_yes or flagged else t("hold.title", lang)
        if said_yes:
            base = t("scam.purchase" if tr.template == "purchase" else "scam.call", lang)
        else:
            base = t("flagged", lang) if flagged else ""
        message = (base + " " + t("bank.callback", lang)).strip()
        if said_yes and guardian and tr.shield:
            message += " " + t("family.informed", lang, name=guardian)
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
        guardian_name=guardian, balance=c.balance, release_at=tr.release_at if tr.status == "delayed" else None,
        analysis=delay.view(tr.analysis, lang),
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


def _start_family(tr: Transfer, c: Client, link: FamilyLink) -> None:
    now = time.time()
    fr = FamilyRequest(STATE.new_id("FR"), tr.id, c.id, link.guardian_id, now, now + FAMILY_TIMEOUT_S)
    STATE.family[fr.id] = fr
    tr.family_request_id = fr.id
    tr.status = "awaiting_family"
    family.notify_request(fr)
    g = STATE.clients[link.guardian_id].short
    total = STATE.session_total(c.id)
    extra = f" (за сутки новым получателям — {_fmt(total)})" if total > tr.amount else ""
    STATE.emit("family", c.id, f"Семейный щит: {g} получил(а) уведомление — перевод {_fmt(tr.amount)}{extra} ждёт решения")


def _hold(tr: Transfer, c: Client, text: str) -> None:
    tr.status = "held"
    STATE.mark_saved(tr)
    STATE.emit("held", c.id, text, step=_step_for(tr), stopped=True)


# ---------------------------------------------------------------------------- meta

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": app.version, "llm": llm.status(),
            "director_protected": bool(os.getenv("QAQPAN_DIRECTOR_KEY")), "locked": os.getenv("QAQPAN_LOCK") == "1",
            "idle_reset_min": float(os.getenv("QAQPAN_IDLE_RESET_MIN", "0") or 0), "shadow": SHADOW()}


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
    _idle_reset()
    with STATE.lock:
        STATE.expire_family()
        STATE.release_delayed()
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
            # director commands are one-shot: a page opened later must not replay them
            "nav": STATE.nav[cid] if STATE.nav[cid] and time.time() * 1000 - STATE.nav[cid]["seq"] < NAV_TTL_MS else None,
            "history": [{"title": h["title"][c.lang], "amount": h["amount"], "ts": time.time() - h["ago_min"] * 60}
                        for h in STATE.history.get(cid, [])],
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
    if res.scheme == "relative":  # «мама, это я, новый номер»: the family code word beats any analysis
        res.tip = t("codeword.ask" if cid in STATE.codewords else "codeword.setup", req.lang)
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
        on_call, recent_call = STATE.pressure(c.id)
        known = STATE.is_known(c.id, acc.number, now)
        a = assess(c, acc, req.amount, on_call, req.context.pasted, req.context.app_switches,
                   recent_call=recent_call, known=known, loan=c.loan, ts=now)
        # family shield: a new recipient (or her own card in another bank under pressure — the usual first hop) and
        # >= the limit in 24 h — splitting into parts, hanging up first or a test transfer of 100 ₸ does not help
        link = STATE.link_for_ward(c.id)
        risky_recipient = not known or "OWN_OTHER_BANK" in a.reasons
        shield = bool(link and risky_recipient and STATE.session_total(c.id, now) + req.amount >= link.limit)
        tr = Transfer(STATE.new_id("TR"), c.id, acc.number, req.amount, now, a.score, a.level,
                      a.reasons, a.kw, a.template, status="completed", shield=shield, pressure=on_call or recent_call)
        STATE.transfers[tr.id] = tr
        STATE.prefill[c.id] = None
        why = ", ".join(reason_text(r, "ru", **a.kw) for r in a.reasons if r != "KNOWN_RECIPIENT")
        flagged = a.level >= 2 and any(r in FLAGGED for r in a.reasons)
        STATE.emit("transfer", c.id, f"{c.short}: перевод {_fmt(req.amount)} → {acc.holder} · риск {a.score:.2f}"
                   + (f" ({why})" if why else ""), step="received" if flagged and not SHADOW() else None)
        if SHADOW() and (a.level or shield):
            # pilot mode: score and log, never delay a real client's money
            would = "семейный щит" if shield else "пауза и вопросы" if a.level >= 2 else "предупреждение"
            STATE.emit("shadow", c.id, f"Теневой режим: перевод {_fmt(req.amount)} прошёл, Qaqpan бы включил: {would}")
            a.level = 0
            shield = tr.shield = False
        if a.level == 0 and not shield:
            c.balance -= req.amount
            STATE.first_paid.setdefault((c.id, acc.number), now)
            tr.status = "completed"
        else:
            STATE.alert(c.id, f"Перевод {_fmt(req.amount)} — Qaqpan поставил на паузу",
                        f"{_fmt(req.amount)} аударым — Qaqpan тоқтатты")
            if a.level >= 2:
                tr.status = "questions"
            elif shield and link:
                _start_family(tr, c, link)
            else:
                tr.status = "warning"
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
        link = STATE.link_for_ward(c.id)
        if said_yes:
            # the client confirmed the pressure herself: the bank decides, the guardian is informed but cannot approve
            tr.level = 3
            tr.reasons.append("SAID_YES")
            _hold(tr, c, f"{c.short}: подтвердил(а) признаки обмана — перевод {_fmt(tr.amount)} остановлен, решение за банком")
            if link and tr.shield:
                family.notify_confirmed(c.id, tr)
        elif tr.shield and link:
            # works even if the scammer coached the victim to answer «no»
            _start_family(tr, c, link)
        elif flagged:
            _hold(tr, c, f"{c.short}: перевод {_fmt(tr.amount)} остановлен — счёт получателя в жалобах")
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
        STATE.mark_saved(tr)
        c = STATE.clients[tr.client_id]
        STATE.emit("cancel", c.id, f"{c.short}: отменил(а) перевод {_fmt(tr.amount)} после предупреждения Qaqpan",
                   step=_step_for(tr), stopped=True)
        return _view(tr)


def _analyse_later(st: State, tid: str, lang: str) -> None:
    tr = st.transfers.get(tid)
    if tr is None or tr.status != "delayed":
        return
    result = delay.analyse(st, tr, lang)
    with st.lock:
        tr.analysis = result
        names = {"likely_scam": "похоже на обман", "unclear": "есть сомнения", "likely_ok": "явных признаков нет"}
        st.emit("analysis", tr.client_id, f"Qaqpan за час: {names[result['verdict']]} — "
                + ", ".join(c.lower() for c in result["codes"]), stopped=result["verdict"] == "likely_scam")


@app.post("/api/transfers/{tid}/delay", response_model=TransferView)
def delay_transfer(tid: str, background: BackgroundTasks) -> TransferView:
    """«Отложить на час»: softer than a block — the money goes out by itself after an hour unless cancelled,
    and Qaqpan analyses the whole session meanwhile."""
    with STATE.lock:
        tr = _transfer(tid)
        if tr.status != "warning":
            raise HTTPException(409, f"Перевод уже в статусе {tr.status}")
        c = STATE.clients[tr.client_id]
        tr.status, tr.release_at = "delayed", time.time() + DELAY_S
        STATE.alert(c.id, f"Перевод {_fmt(tr.amount)} отложен на час", f"{_fmt(tr.amount)} аударым бір сағатқа қалдырылды")
        STATE.emit("delay", c.id, f"{c.short}: перевод {_fmt(tr.amount)} отложен на час — Qaqpan анализирует сессию")
        link = STATE.link_for_ward(c.id)
        if link:
            family.notify_delayed(c.id, tr)
        background.add_task(_analyse_later, current(), tr.id, c.lang)
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
        STATE.first_paid.setdefault((c.id, tr.account), time.time())
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
        if req.client_id != fr.guardian_id:  # the ward (or a scammer holding her phone) cannot approve for the son
            raise HTTPException(403, "Решение принимает только доверенное лицо")
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
                STATE.first_paid.setdefault((c.id, tr.account), time.time())
                STATE.emit("family_ok", c.id, f"{g.short} подтвердил(а) перевод {_fmt(tr.amount)}")
            else:
                tr.status, tr.note = "cancelled", "insufficient"
                STATE.emit("family_ok", c.id, f"{g.short} подтвердил(а), но средств уже не хватает — перевод отменён")
        else:
            fr.status = "declined"
            tr.status = "cancelled"
            STATE.mark_saved(tr)
            # the guardian's «no» is a signal, not a complaint: it may be an honest seller (a sofa, a car).
            # The account is flagged for everyone only when the ward confirms with a complaint about this transfer.
            acc = STATE.accounts[tr.account]
            if (g.id, acc.number) not in STATE.complaints_by:
                STATE.complaints_by.add((g.id, acc.number))
                acc.signals += 1
            STATE.alert(c.id, f"{g.short} отклонил(а) перевод", f"{g.short} аударымды қабылдамады")
            STATE.emit("family_no", c.id, f"{g.short} отклонил(а) перевод {_fmt(tr.amount)} — деньги {c.short} спасены",
                       step="persuaded", stopped=True)
        return {"status": fr.status, "transfer": _view(tr).model_dump()}


@app.post("/api/family/{cid}/codeword")
def codeword(cid: str, req: CodewordRequest) -> dict:
    """The family agreed on a code word. Qaqpan stores only the fact, never the word."""
    _client(cid)
    with STATE.lock:
        family_ids = {cid} | {lk.guardian_id for lk in STATE.links.values() if lk.ward_id == cid} | \
                     {lk.ward_id for lk in STATE.links.values() if lk.guardian_id == cid}
        for x in family_ids:
            (STATE.codewords.add if req.agreed else STATE.codewords.discard)(x)
        if req.agreed:
            STATE.emit("codeword", cid, f"{STATE.clients[cid].short}: семья договорилась о кодовом слове")
    return {"agreed": req.agreed}


@app.post("/api/recipients/check")
def check_recipient(req: RecipientCheck) -> dict:
    """«Проверить получателя» before paying: only «complaints / no complaints» — never anything about the owner."""
    c = _client(req.client_id)
    num = digits(req.account)
    if not 12 <= len(num) <= 20:
        raise HTTPException(422, "Проверьте номер счёта или карты")
    with STATE.lock:
        acc = STATE.accounts.get(num)  # do not create an account record just for a check
        if acc and acc.owner_id == c.id:
            status = "own"
        elif acc and (acc.complaints or acc.in_afc):
            status = "complaints"
        elif acc and acc.signals:
            status = "signals"
        elif STATE.is_known(c.id, num):
            status = "known"
        else:
            status = "clean"
        STATE.emit("recipient_check", c.id, f"{c.short} проверил(а) получателя перед переводом: {status}")
        return {"status": status, "message": t(f"rcpt.{status}", c.lang)}


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

def _confirmed(tr: Transfer) -> bool:
    """A complaint confirms the account only for a transfer Qaqpan itself stopped under pressure:
    during or right after a call, and the client said «yes» or the guardian declined it."""
    fr = STATE.family.get(tr.family_request_id or "")
    stopped = bool(tr.answers and any(tr.answers)) or bool(fr and fr.status == "declined")
    return tr.pressure and stopped


@app.post("/api/complaints", response_model=ComplaintResult)
def complain(req: ComplaintRequest) -> ComplaintResult:
    c = _client(req.client_id)
    with STATE.lock:
        tr = None
        if req.transfer_id:
            tr = _transfer(req.transfer_id)
            if tr.client_id != c.id:
                raise HTTPException(404, "Перевод не найден")
            acc = STATE.accounts[tr.account]
        elif req.account and 12 <= len(digits(req.account)) <= 20:
            acc = STATE.account(req.account)  # by number only: a signal, one dishonest client cannot hold a seller
        else:
            raise HTTPException(422, "Нужен перевод или номер счёта")
        confirmed = bool(tr and _confirmed(tr))
        key = (c.id, acc.number)
        call = STATE.calls.get(c.id)
        number = call.number if call else STATE.last_call_number.get(c.id)
        if number in (BANK_NUMBER, NATIVE_NUMBER):
            number = None
        if key not in STATE.complaints_by or confirmed and key not in STATE.confirmed_by:  # one client = one complaint
            first = key not in STATE.complaints_by
            STATE.complaints_by.add(key)
            if confirmed:
                STATE.confirmed_by.add(key)
                acc.complaints += 1
                STATE.emit("complaint", c.id, f"Жалоба {c.short} подтверждена остановленным переводом: счёт {acc.display} "
                           "помечен — все, кто попробует туда перевести, получат паузу и вопросы")
            elif first:
                acc.signals += 1
                STATE.emit("complaint", c.id, f"Жалоба {c.short} на счёт {acc.display} — непроверенный сигнал, добавлен к риску")
            if number and first:
                STATE.number_complaints[number] = STATE.number_complaints.get(number, 0) + 1
        return ComplaintResult(message=t("complaint.done" if confirmed else "complaint.signal", c.lang),
                               account_complaints=acc.complaints,
                               confirmed=confirmed, number_flagged=number)


# ---------------------------------------------------------------------------- help

@app.post("/api/victim/help", response_model=VictimHelp)
def victim_help(req: VictimRequest) -> VictimHelp:
    c = _client(req.client_id)
    lang = req.lang or c.lang
    amount = account = None
    tr = STATE.transfers.get(req.transfer_id or "")
    if tr is None or tr.client_id != c.id:  # opened from the home screen: use the latest suspicious transfer
        tr = next((x for x in reversed(list(STATE.transfers.values())) if x.client_id == c.id and x.level >= 2), None)
    attempt = False
    if tr is not None and tr.client_id == c.id:
        amount, account = tr.amount, STATE.accounts[tr.account].display
        attempt = tr.status != "completed"  # stopped by Qaqpan: a report of an attempt, not «I transferred»
    call = STATE.calls.get(c.id)
    phone_no = STATE.last_call_number.get(c.id) or (call.number if call and call.number != NATIVE_NUMBER else None)
    scheme = "полиции / банка" if lang == "ru" else "полиция / банк"
    return victim.build(lang, c.name, amount, account, phone_no, scheme, req.story, attempt)


@app.post("/api/assistant", response_model=assistant.AssistantReply)
def ask_assistant(req: AssistantRequest) -> assistant.AssistantReply:
    c = _client(req.client_id)
    lang = req.lang or c.lang
    res = assistant.answer(c.id, [m.model_dump() for m in req.messages], lang)
    STATE.emit("assistant", c.id, f"{c.short} спросил(а) помощника Qaqpan: «{req.messages[-1].content[:60]}»")
    return res


# ---------------------------------------------------------------------------- stage & director

@app.get("/api/stage")
def stage(since: int = 0) -> dict:
    _idle_reset()
    with STATE.lock:
        STATE.release_delayed()
        return {
            "steps": sorted(STATE.steps),
            "stopped": STATE.stopped,
            "saved": STATE.saved,
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
