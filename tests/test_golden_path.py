"""Golden path: the whole 3-minute demo through the API (docs/DEMO_SCENARIO.md).

Run after every change: `make test`. LLM is forced off so the test is deterministic and offline.
"""

import os

os.environ["QAQPAN_DEMO"] = "1"

import pytest
from fastapi.testclient import TestClient

from api.main import app

c = TestClient(app)
DANIYAR = "KZ86 8562 0000 0471 1934"
SISTER = "KZ55 8562 0000 0128 7740"


@pytest.fixture(autouse=True)
def reset():
    c.post("/api/director/reset")


def test_health():
    assert c.get("/api/health").json()["status"] == "ok"


def test_golden_path():
    # 1 «Написали»: SMS about ЭЦП -> scam, in Kazakh for Aigerim
    c.post("/api/director/sms")
    sms = c.get("/api/phone/aigerim").json()["sms"][0]
    r = c.post("/api/messages/check", json={"client_id": "aigerim", "sample_id": sms["sample_id"], "lang": "kk"}).json()
    assert r["verdict"] == "scam" and r["scheme"] == "ecp_egov"

    # 2 «Позвонили»: fake bank call -> bank is NOT calling
    c.post("/api/director/call")
    c.post("/api/phone/aigerim/call/answer")
    v = c.post("/api/calls/verify", json={"client_id": "aigerim"}).json()
    assert v["status"] == "not_bank" and v["number_complaints"] >= 1

    # 3 «Уговорили»: 900 000 to a new account during the call -> questions
    tr = c.post("/api/transfers", json={"client_id": "aigerim", "account": DANIYAR, "amount": 900_000}).json()
    assert tr["status"] == "questions" and tr["level"] == 2 and len(tr["questions"]) == 3
    assert "Данияр" not in (tr["message"] or "")  # never reveal anything about the recipient's operations

    # scammer coached her to answer «no» — the family shield still stops it
    tr = c.post(f"/api/transfers/{tr['id']}/answers", json={"answers": [False, False, False]}).json()
    assert tr["status"] == "awaiting_family" and tr["guardian_name"] == "Ержан"
    req = c.get("/api/phone/erzhan").json()["family_requests"][0]
    assert req["amount"] == 900_000
    d = c.post(f"/api/family/requests/{req['id']}/decision", json={"approve": False}).json()
    assert d["transfer"]["status"] == "cancelled"
    assert c.get("/api/phone/aigerim").json()["client"]["balance"] == 1_350_000

    # 4 «Получили»: her complaint marks the account -> Madina is protected 10 seconds later
    comp = c.post("/api/complaints", json={"client_id": "aigerim", "transfer_id": tr["id"]}).json()
    assert comp["account_complaints"] == 2  # the son's «no» + the mother's complaint
    m = c.post("/api/transfers", json={"client_id": "madina", "account": DANIYAR, "amount": 150_000}).json()
    assert m["status"] == "questions" and "жалоб" in m["message"]
    m = c.post(f"/api/transfers/{m['id']}/answers", json={"answers": [True, True, False]}).json()
    assert m["status"] == "held"

    stage = c.get("/api/stage").json()
    assert set(stage["steps"]) == {"written", "called", "persuaded", "received"}
    assert stage["stopped"] >= 4


def test_normal_transfer_passes():
    tr = c.post("/api/transfers", json={"client_id": "aigerim", "account": SISTER, "amount": 50_000}).json()
    assert tr["status"] == "completed" and tr["level"] == 0


def test_real_bank_call_is_confirmed():
    c.post("/api/director/bank_calls_madina")
    c.post("/api/phone/madina/call/answer")
    v = c.post("/api/calls/verify", json={"client_id": "madina"}).json()
    assert v["status"] == "bank" and "Асем" in v["message"]


def test_family_timeout_escalates_not_blocks(monkeypatch):
    c.post("/api/director/call")
    c.post("/api/phone/aigerim/call/answer")
    tr = c.post("/api/transfers", json={"client_id": "aigerim", "account": DANIYAR, "amount": 900_000}).json()
    c.post(f"/api/transfers/{tr['id']}/answers", json={"answers": [True, False, False]})
    import api.state as st
    for fr in st.STATE.family.values():
        fr.expires = 0
    assert c.get("/api/phone/aigerim").json()["transfers"][-1]["status"] == "escalated"


def test_legit_bank_sms_is_safe():
    r = c.post("/api/messages/check", json={"sample_id": "legit_otp"}).json()
    assert r["verdict"] == "safe"


def test_victim_help_template_offline():
    h = c.post("/api/victim/help", json={"client_id": "aigerim", "lang": "ru"}).json()
    assert len(h["steps"]) == 4 and "Заявление" in h["statement"]["title"]


def test_schemes_have_sources():
    for card in c.get("/api/schemes?lang=kk").json():
        assert card["source"].startswith("https://")


def test_native_call_signal_raises_transfer_risk():
    c.post("/api/phone/aigerim/native-call", json={"on_call": True})
    assert c.get("/api/phone/aigerim").json()["call"]["answered"] is True
    tr = c.post("/api/transfers", json={"client_id": "aigerim", "account": DANIYAR, "amount": 900_000}).json()
    assert tr["level"] == 2
    c.post("/api/phone/aigerim/native-call", json={"on_call": False})
    assert c.get("/api/phone/aigerim").json()["call"] is None


def test_reset_bumps_epoch():
    e = c.get("/api/phone/aigerim").json()["epoch"]
    c.post("/api/director/reset")
    assert c.get("/api/phone/aigerim").json()["epoch"] == e + 1
