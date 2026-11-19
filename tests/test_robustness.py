"""Regression tests for every bug found in the audit + the family shield behaviour."""

import os
import time

os.environ["QAQPAN_DEMO"] = "1"

import pytest
from fastapi.testclient import TestClient

from api import llm
from api.main import app
from api.state import STATE

c = TestClient(app)
SCAM = "KZ86 8562 0000 0471 1934"
OWN_CARD = "5169 4971 0023 7781"


@pytest.fixture(autouse=True)
def reset():
    c.post("/api/director/reset")


def scam_transfer_to_family(answers=(False, False, False)):
    c.post("/api/director/call")
    c.post("/api/phone/aigerim/call/answer")
    tr = c.post("/api/transfers", json={"client_id": "aigerim", "account": SCAM, "amount": 900_000}).json()
    return c.post(f"/api/transfers/{tr['id']}/answers", json={"answers": list(answers)}).json()


# ---------------------------------------------------------------- bugs from the audit

def test_own_transfers_stay_visible_when_others_transfer():
    tr = c.post("/api/transfers", json={"client_id": "aigerim", "account": SCAM, "amount": 10_000}).json()
    for i in range(6):
        c.post("/api/transfers", json={"client_id": "madina", "account": f"KZ21 8562 0000 0390 55{10 + i}", "amount": 1000 + i})
    ids = [t["id"] for t in c.get("/api/phone/aigerim").json()["transfers"]]
    assert tr["id"] in ids


def test_approve_without_funds_cancels_instead_of_hanging():
    tr = scam_transfer_to_family()
    STATE.clients["aigerim"].balance = 100
    rid = c.get("/api/phone/erzhan").json()["family_requests"][0]["id"]
    d = c.post(f"/api/family/requests/{rid}/decision", json={"approve": True}).json()
    msg = d["transfer"]["message"]
    assert d["transfer"]["status"] == "cancelled" and ("средств" in msg or "қаражат" in msg)
    assert tr["id"] == d["transfer"]["id"]


def test_cancel_withdraws_the_family_request():
    tr = scam_transfer_to_family()
    c.post(f"/api/transfers/{tr['id']}/cancel")
    son = c.get("/api/phone/erzhan").json()
    assert son["family_requests"] == [] and son["notices"] == []


def test_decision_on_closed_request_is_rejected():
    tr = scam_transfer_to_family()
    rid = c.get("/api/phone/erzhan").json()["family_requests"][0]["id"]
    c.post(f"/api/transfers/{tr['id']}/cancel")
    assert c.post(f"/api/family/requests/{rid}/decision", json={"approve": True}).status_code == 409


def test_complaints_are_counted_once_per_client():
    tr = scam_transfer_to_family()
    for _ in range(3):
        r = c.post("/api/complaints", json={"client_id": "aigerim", "transfer_id": tr["id"]}).json()
    assert r["account_complaints"] == 1
    assert STATE.number_complaints["+7 727 356 18 40"] == 4  # 3 seeded + 1


def test_call_check_does_not_accuse_an_unknown_caller():
    c.post("/api/phone/aigerim/native-call", json={"on_call": True})
    v = c.post("/api/calls/verify", json={"client_id": "aigerim", "lang": "ru"}).json()
    assert v["status"] == "not_bank" and "Если собеседник представился банком" in v["message"]
    assert v["number"] is None and v["number_complaints"] == 0


@pytest.mark.parametrize("account", ["abc", "123", "KZ86 8562", "1" * 25])
def test_invalid_account_is_rejected(account):
    r = c.post("/api/transfers", json={"client_id": "aigerim", "account": account + "      ", "amount": 1000})
    assert r.status_code == 422 and "номер" in r.json()["detail"]


def test_double_tap_creates_one_transfer():
    body = {"client_id": "aigerim", "account": SCAM, "amount": 25_000}
    a, b = c.post("/api/transfers", json=body).json(), c.post("/api/transfers", json=body).json()
    assert a["id"] == b["id"]


def test_unknown_api_path_is_404_not_the_web_app():
    assert c.get("/api/does-not-exist").status_code == 404


def test_director_key_protects_the_demo(monkeypatch):
    monkeypatch.setenv("QAQPAN_DIRECTOR_KEY", "s3cret")
    assert c.post("/api/director/reset").status_code == 403
    assert c.post("/api/director/reset", headers={"X-Director-Key": "wrong"}).status_code == 403
    assert c.post("/api/director/reset", headers={"X-Director-Key": "s3cret"}).status_code == 200


def test_llm_spend_guard(monkeypatch):
    monkeypatch.setattr(llm, "RPM", 2)
    monkeypatch.setattr(llm, "_recent", type(llm._recent)())
    monkeypatch.setattr(llm, "_daily", {})
    assert llm._allow_live_call() and llm._allow_live_call() and not llm._allow_live_call()


# ---------------------------------------------------------------- family shield

def test_guardian_sees_plain_explanation_timeline_and_push():
    c.post("/api/director/sms")
    c.post("/api/messages/check", json={"client_id": "aigerim", "sample_id": "ecp", "lang": "kk"})
    scam_transfer_to_family()
    son = c.get("/api/phone/erzhan").json()
    req = son["family_requests"][0]
    assert req["headline"].startswith("Маму")
    assert "говорит по телефону" in req["explanation"] and "подсказывают" in req["explanation"]
    assert req["ward_phone"].startswith("+7")
    texts = [x["text"] for x in req["timeline"]]
    assert any("мошенничество" in x for x in texts) and any("звонок" in x for x in texts)
    push = son["notices"][0]
    assert push["kind"] == "family_request" and "900 000" in push["body"]
    c.post(f"/api/phone/erzhan/notices/{push['id']}/seen")
    assert c.get("/api/phone/erzhan").json()["notices"] == []


def test_own_card_in_other_bank_goes_to_family():
    c.post("/api/director/call")
    c.post("/api/phone/aigerim/call/answer")
    tr = c.post("/api/transfers", json={"client_id": "aigerim", "account": OWN_CARD, "amount": 1_000_000}).json()
    assert tr["status"] == "questions"
    c.post(f"/api/transfers/{tr['id']}/answers", json={"answers": [False, False, False]})
    req = c.get("/api/phone/erzhan").json()["family_requests"][0]
    assert "свою карту в другом банке" in req["explanation"]


def test_shield_cannot_be_switched_off_instantly():
    r = c.post("/api/family/aigerim/disable").json()
    assert r["disable_at"] - time.time() > 23 * 3600
    son = c.get("/api/phone/erzhan").json()
    assert son["notices"][0]["kind"] == "shield_disable"
    assert son["shield"]["wards"][0]["disable_at"]
    # still protected during the 24 hours
    assert scam_transfer_to_family()["status"] == "awaiting_family"
    c.post("/api/family/aigerim/keep")
    assert c.get("/api/phone/aigerim").json()["shield"]["disable_at"] is None


def test_after_24h_shield_is_off_and_bank_takes_over():
    c.post("/api/family/aigerim/disable")
    STATE.links["aigerim"].disable_at = time.time() - 1
    tr = scam_transfer_to_family(answers=(True, False, False))
    assert tr["status"] == "held"


def test_shield_info_roles():
    assert c.get("/api/phone/aigerim").json()["shield"]["role"] == "ward"
    assert c.get("/api/phone/erzhan").json()["shield"]["role"] == "guardian"
    assert c.get("/api/phone/madina").json()["shield"]["role"] == "none"


def test_guardian_decline_alone_protects_the_next_client():
    scam_transfer_to_family()
    rid = c.get("/api/phone/erzhan").json()["family_requests"][0]["id"]
    c.post(f"/api/family/requests/{rid}/decision", json={"approve": False})
    m = c.post("/api/transfers", json={"client_id": "madina", "account": SCAM, "amount": 150_000}).json()
    assert m["status"] == "questions" and "жалоб" in m["message"]


def test_director_navigation_is_not_replayed_on_reload():
    c.post("/api/director/transfer_aigerim")
    assert c.get("/api/phone/aigerim").json()["nav"]["screen"] == "transfer"
    STATE.nav["aigerim"]["seq"] -= 60_000  # a minute later the page is reopened
    assert c.get("/api/phone/aigerim").json()["nav"] is None


def test_history_is_localised():
    c.post("/api/phone/aigerim/lang/kk")
    titles = [h["title"] for h in c.get("/api/phone/aigerim").json()["history"]]
    assert "Қызынан аударым" in titles
