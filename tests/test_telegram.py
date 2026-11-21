"""Telegram bot: message check rendering, linking the son, the son's decision from Telegram (Telegram API faked)."""

import os

os.environ["QAQPAN_DEMO"] = "1"

import pytest
from fastapi.testclient import TestClient

from api import msgcheck, tgbot
from api.main import app

c = TestClient(app)
SID = "tgtestsandbox1"
H = {"X-Qaqpan-Session": SID}
SCAM = "KZ86 8562 0000 0471 1934"


@pytest.fixture
def tg(monkeypatch):
    sent: list[dict] = []
    monkeypatch.setattr(tgbot, "TOKEN", "test")
    monkeypatch.setattr(tgbot, "call", lambda method, **p: sent.append({"method": method, **p}) or {"ok": True, "result": {}})
    monkeypatch.setattr(tgbot, "send_later", lambda *a, **k: tgbot.send(*a, **k))
    monkeypatch.setattr(tgbot, "_links", {})
    return sent


def test_render_marks_the_message_and_numbers_the_reasons():
    res = msgcheck.check_rules("Срочно! Назовите код из SMS. Продлите ЭЦП: egov-kz.online/ecp", "ru")
    out = tgbot.render(res, "ru")
    assert out.startswith("🔴 <b>Мошенничество</b>")
    assert "<u><b>egov-kz.online/ecp</b></u>" in out and "①" in out and "Где подвох" in out


def test_a_forwarded_sms_gets_a_verdict(tg):
    tgbot.on_message({"chat": {"id": 7}, "from": {"language_code": "ru"}, "text": "Ваша карта заблокирована. Назовите код из SMS"})
    assert tg[-1]["method"] == "sendMessage" and "Мошенничество" in tg[-1]["text"]


def test_the_son_decides_from_telegram(tg):
    c.post("/api/director/reset", headers=H)
    tgbot.on_message({"chat": {"id": 42}, "from": {}, "text": f"/start g_{SID}"})
    assert "Ержан" in tg[-1]["text"]
    c.post("/api/director/call", headers=H)
    c.post("/api/phone/aigerim/call/answer", headers=H)
    tr = c.post("/api/transfers", json={"client_id": "aigerim", "account": SCAM, "amount": 900_000}, headers=H).json()
    c.post(f"/api/transfers/{tr['id']}/answers", json={"answers": [False] * 3}, headers=H)
    push = next(m for m in tg if m["method"] == "sendMessage" and m["chat_id"] == 42 and "reply_markup" in m)
    decline = push["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    assert decline.startswith(f"fd:{SID}:")
    tgbot.on_callback({"id": "cb1", "data": decline, "message": {"chat": {"id": 42}, "message_id": 1}})
    assert c.get("/api/phone/aigerim", headers=H).json()["transfers"][-1]["status"] == "cancelled"
    assert "отклонили" in tg[-1]["text"]
    assert c.get("/api/phone/aigerim").json()["transfers"] == []  # the shared stage is untouched


def test_bot_is_off_without_a_token():
    assert tgbot.status()["enabled"] is False
