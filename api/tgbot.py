"""Qaqpan in Telegram: the same protection where people actually get scam messages.

Two jobs:
  1. Check a message: forward an SMS / WhatsApp text or a screenshot -> verdict with the «где подвох»
     marks and reasons, the same engine as the app (rules + AI, never softer than the rules).
  2. Be the son in the demo: /start g_<sandbox> links this chat as Erzhan, the guardian. When Qaqpan stops
     the mother's transfer, the push with «Отклонить / Разрешить» arrives in this real Telegram.

Runs inside the single API process (long polling in a daemon thread), only when TELEGRAM_BOT_TOKEN is set.
No message text is stored; links live in memory like the rest of the demo.
"""

from __future__ import annotations

import base64
import html
import logging
import os
import threading
import time

import httpx

from . import msgcheck
from .state import SANDBOX_ID, State, _shared, current, sandbox, use_state

log = logging.getLogger("qaqpan.tg")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API = f"https://api.telegram.org/bot{TOKEN}"
GUARDIAN = "erzhan"
NUM = "①②③④⑤⑥⑦⑧"
ICON = {"scam": "🔴", "suspicious": "🟠", "safe": "🟢"}
LABEL = {"scam": {"ru": "Мошенничество", "kk": "Алаяқтық"}, "suspicious": {"ru": "Подозрительно", "kk": "Күдікті"},
         "safe": {"ru": "Явных признаков нет", "kk": "Айқын белгілер жоқ"}}

_me: dict | None = None
_links: dict[int, tuple[int, str]] = {}   # id(State) -> (chat_id, sandbox id or "-")
_langs: dict[int, str] = {}
_started = False


def enabled() -> bool:
    return bool(TOKEN)


def status() -> dict:
    return {"enabled": enabled(), "username": (_me or {}).get("username")}


def call(method: str, **params) -> dict:
    r = httpx.post(f"{API}/{method}", json=params, timeout=35)
    return r.json()


def send(chat_id: int, text: str, buttons: list[list[tuple[str, str]]] | None = None) -> None:
    params: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if buttons:
        params["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]}
    call("sendMessage", **params)


def send_later(*args, **kw) -> None:
    """Never block an API request on Telegram."""
    if enabled():
        threading.Thread(target=lambda: _safe(send, *args, **kw), daemon=True).start()


def _safe(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except Exception as e:  # noqa: BLE001 — the bot must never take the API down
        log.warning("telegram: %s", e)


# ---------------------------------------------------------------- message check

def render(res: msgcheck.CheckResult, lang: str) -> str:
    """The verdict as Telegram HTML: the message with numbered marks, then the numbered reasons."""
    head = f"{ICON[res.verdict]} <b>{LABEL[res.verdict][lang]}</b>" + (f" · {html.escape(res.scheme_name)}" if res.scheme_name else "")
    lines = [head]
    text = (res.text or "")[:700]
    marked = sorted([r for r in res.reasons if r.spans], key=lambda r: min(a for a, _ in r.spans))
    if text and marked:
        owner: list[int | None] = [None] * len(text)
        for n, r in enumerate(marked):
            for a, b in r.spans:
                for k in range(max(0, a), min(len(text), b)):
                    if owner[k] is None:
                        owner[k] = n
        out, k, seen = [], 0, set()
        while k < len(text):
            n = owner[k]
            j = k
            while j < len(text) and owner[j] == n:
                j += 1
            chunk = html.escape(text[k:j])
            if n is None:
                out.append(chunk)
            else:
                out.append(f"<u><b>{chunk}</b></u>" + ("" if n in seen else NUM[n]))
                seen.add(n)
            k = j
        lines += ["", "<b>" + ("Алдау қай жерде" if lang == "kk" else "Где подвох") + "</b>", "<i>" + "".join(out) + "</i>"]
    lines.append("")
    lines += [f"{NUM[n]} {html.escape(r.text)}" for n, r in enumerate(marked)]
    lines += [f"• {html.escape(r.text)}" for r in res.reasons if not r.spans]
    if res.tip:
        lines += ["", f"🔑 {html.escape(res.tip)}"]
    lines += ["", f"💡 {html.escape(res.advice)}"]
    return "\n".join(lines)


GREETING = {
    "ru": ("<b>Qaqpan</b> — капкан для мошенников.\n\nПерешлите сюда подозрительное SMS, сообщение из WhatsApp или "
           "скриншот — скажу, мошенники ли это, и покажу, где подвох.\n\nВ демо можно стать сыном клиентки банка: "
           "отсканируйте QR на странице qaqpan — и уведомление «Маму, возможно, обманывают» придёт сюда."),
    "kk": ("<b>Qaqpan</b> — алаяқтарға арналған қақпан.\n\nКүдікті SMS, WhatsApp хабарламасын немесе скриншотты осында "
           "жіберіңіз — алаяқтар ма, айтамын және алдау қай жерде екенін көрсетемін."),
}


def _lang(user: dict | None) -> str:
    return "kk" if (user or {}).get("language_code", "").startswith("kk") else "ru"


def on_message(msg: dict) -> None:
    chat = msg["chat"]["id"]
    lang = _langs.setdefault(chat, _lang(msg.get("from")))
    text = (msg.get("text") or msg.get("caption") or "").strip()
    if text.startswith("/start"):
        arg = text.split(maxsplit=1)[1] if " " in text else ""
        if arg.startswith("g_"):
            return link_guardian(chat, arg[2:], lang)
        return send(chat, GREETING[lang])
    if text.startswith("/stop"):
        for k, (c, _) in list(_links.items()):
            if c == chat:
                del _links[k]
        return send(chat, "Уведомления отключены." if lang == "ru" else "Хабарламалар өшірілді.")
    image = None
    if msg.get("photo"):
        send(chat, "Читаю скриншот…" if lang == "ru" else "Скриншотты оқып жатырмын…")
        image = _download(msg["photo"][-1]["file_id"])
    if not text and not image:
        return send(chat, GREETING[lang])
    res = msgcheck.check(text or None, image, "image/jpeg", None, lang)
    send(chat, render(res, lang))


def _download(file_id: str) -> str | None:
    path = call("getFile", file_id=file_id).get("result", {}).get("file_path")
    if not path:
        return None
    data = httpx.get(f"https://api.telegram.org/file/bot{TOKEN}/{path}", timeout=30).content
    return base64.standard_b64encode(data).decode()


# ---------------------------------------------------------------- the son in the demo

def _state(sid: str) -> State:
    return sandbox(sid) if SANDBOX_ID.fullmatch(sid) else _shared


def link_guardian(chat: int, sid: str, lang: str) -> None:
    st = _state(sid)
    _links[id(st)] = (chat, sid if SANDBOX_ID.fullmatch(sid) else "-")
    send(chat, "✅ Готово: в демо вы — <b>Ержан</b>, сын Айгерим.\n\nКогда Qaqpan остановит подозрительный перевод мамы, "
               "уведомление придёт сюда — с объяснением простыми словами и кнопками «Отклонить / Разрешить».")


def guardian_chat() -> tuple[int, str] | None:
    return _links.get(id(current()))


def push_family_request(view: dict) -> None:
    """Called by the family module when a transfer waits for the son."""
    link = guardian_chat()
    if not link:
        return
    chat, sid = link
    body = (f"🛡 <b>{html.escape(view['headline'])}</b>\n\n{html.escape(view['explanation'])}\n\n"
            f"💸 {view['amount']:,.0f} ₸ → {html.escape(view['holder'])}\n\n{html.escape(view['advice'])}").replace(",", " ")
    send_later(chat, body, [[("❌ Отклонить перевод", f"fd:{sid}:{view['id']}")], [("Разрешить…", f"fa:{sid}:{view['id']}")]])


def push_text(text: str) -> None:
    link = guardian_chat()
    if link:
        send_later(link[0], f"🛡 {html.escape(text)}")


def on_callback(cb: dict) -> None:
    kind, sid, rid = (cb.get("data") or "::").split(":", 2)
    msg = cb.get("message") or {}
    chat, mid = msg.get("chat", {}).get("id"), msg.get("message_id")
    if kind == "fa":  # «Разрешить» asks once more: the son must talk to his mother first
        call("answerCallbackQuery", callback_query_id=cb["id"])
        call("editMessageReplyMarkup", chat_id=chat, message_id=mid, reply_markup={"inline_keyboard": [
            [{"text": "Да, я поговорил с мамой — разрешить", "callback_data": f"fy:{sid}:{rid}"}],
            [{"text": "❌ Нет, отклонить", "callback_data": f"fd:{sid}:{rid}"}]]})
        return
    approve = kind == "fy"
    from .main import family_decision  # late import: main imports this module
    from .schemas import FamilyDecision
    token = use_state(_state(sid) if sid != "-" else None)
    try:
        family_decision(rid, FamilyDecision(client_id=GUARDIAN, approve=approve))
        result = ("✅ Вы разрешили перевод." if approve else "❌ Вы отклонили перевод — деньги мамы в безопасности.")
    except Exception as e:  # noqa: BLE001 — closed, expired or unknown request
        result = f"Запрос уже закрыт ({getattr(e, 'detail', e)})"
    finally:
        from .state import _current
        _current.reset(token)
    call("answerCallbackQuery", callback_query_id=cb["id"], text=result[:180])
    call("editMessageReplyMarkup", chat_id=chat, message_id=mid, reply_markup={"inline_keyboard": []})
    send(chat, result)


# ---------------------------------------------------------------- polling

def handle(update: dict) -> None:
    if "callback_query" in update:
        _safe(on_callback, update["callback_query"])
    elif "message" in update:
        _safe(on_message, update["message"])


def _loop() -> None:
    global _me
    _me = (_safe(call, "getMe") or {}).get("result")
    log.info("telegram bot @%s polling", (_me or {}).get("username"))
    offset = 0
    while True:
        try:
            r = call("getUpdates", offset=offset, timeout=25, allowed_updates=["message", "callback_query"])
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                threading.Thread(target=handle, args=(u,), daemon=True).start()
        except Exception as e:  # noqa: BLE001
            log.warning("telegram polling: %s", e)
            time.sleep(5)


def start() -> None:
    """One poller per token: run the bot on the deployment only (QAQPAN_TELEGRAM=0 switches it off elsewhere)."""
    global _started
    if enabled() and not _started and os.getenv("QAQPAN_TELEGRAM", "1") != "0":
        _started = True
        threading.Thread(target=_loop, daemon=True, name="telegram").start()
