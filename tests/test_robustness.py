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
SISTER_OF_NOBODY = "KZ44 8562 0000 0777 1234"


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
    d = c.post(f"/api/family/requests/{rid}/decision", json={"client_id": "erzhan", "approve": True}).json()
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
    assert c.post(f"/api/family/requests/{rid}/decision", json={"client_id": "erzhan", "approve": True}).status_code == 409


def test_complaints_are_counted_once_per_client():
    tr = scam_transfer_to_family(answers=(True, False, False))  # she confirmed the pressure -> a confirmed complaint
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


def test_guardian_decline_alone_is_a_signal_not_a_hold():
    # the son may decline an honest seller (a sofa): his «no» alone must not hold everyone's payments
    scam_transfer_to_family()
    rid = c.get("/api/phone/erzhan").json()["family_requests"][0]["id"]
    c.post(f"/api/family/requests/{rid}/decision", json={"client_id": "erzhan", "approve": False})
    m = c.post("/api/transfers", json={"client_id": "madina", "account": SCAM, "amount": 150_000}).json()
    assert m["status"] == "warning" and "жалоб" not in (m["message"] or "")


def test_director_navigation_is_not_replayed_on_reload():
    c.post("/api/director/transfer_aigerim")
    assert c.get("/api/phone/aigerim").json()["nav"]["screen"] == "transfer"
    STATE.nav["aigerim"]["seq"] -= 60_000  # a minute later the page is reopened
    assert c.get("/api/phone/aigerim").json()["nav"] is None


def test_history_is_localised():
    c.post("/api/phone/aigerim/lang/kk")
    titles = [h["title"] for h in c.get("/api/phone/aigerim").json()["history"]]
    assert "Қызынан аударым" in titles


def test_victim_help_for_a_stopped_transfer_reports_an_attempt():
    scam_transfer_to_family()
    h = c.post("/api/victim/help", json={"client_id": "aigerim", "lang": "ru"}).json()
    body = h["statement"]["body"]
    assert "900 000" in body and "KZ86" in body and "попытк" in body and "перевел(а)" not in body


def test_victim_help_after_a_completed_transfer_is_a_loss_statement():
    tr = c.post("/api/transfers", json={"client_id": "madina", "account": SCAM, "amount": 40_000}).json()
    assert tr["status"] == "completed"
    h = c.post("/api/victim/help", json={"client_id": "madina", "lang": "ru", "transfer_id": tr["id"]}).json()
    assert "перевел(а) 40 000" in h["statement"]["body"]


def test_assistant_offline_knows_the_call_situation():
    c.post("/api/director/call")
    c.post("/api/phone/aigerim/call/answer")
    r = c.post("/api/assistant", json={"client_id": "aigerim", "lang": "ru",
                                       "messages": [{"role": "user", "content": "Мне звонят из службы безопасности банка"}]}).json()
    assert r["source"] in ("offline", "llm", "cache") and r["reply"]


def test_assistant_offline_answers_without_ai(monkeypatch):
    monkeypatch.delenv("XKIRO_API_KEY", raising=False)
    r = c.post("/api/assistant", json={"client_id": "madina", "lang": "ru",
                                       "messages": [{"role": "user", "content": "Продавец на OLX просит предоплату"}]}).json()
    assert r["source"] == "offline" and "предоплат" in r["reply"]
    from api.assistant import offline_reply
    c.post("/api/director/call"); c.post("/api/phone/aigerim/call/answer")
    assert offline_reply("aigerim", "что делать", "ru").startswith("Вижу, что вам сейчас звонят")


# ---------------------------------------------------------------- review 21.11: bypasses of the shield

def on_call():
    c.post("/api/phone/aigerim/lang/ru")
    c.post("/api/director/call")
    c.post("/api/phone/aigerim/call/answer")


def send(amount, account=SCAM, cid="aigerim"):
    return c.post("/api/transfers", json={"client_id": cid, "account": account, "amount": amount}).json()


def test_split_transfers_reach_family():
    on_call()
    first = send(180_000)
    first = c.post(f"/api/transfers/{first['id']}/answers", json={"answers": [False] * 3}).json()
    assert first["status"] == "warning"  # 180 000 is under the 200 000 limit
    c.post(f"/api/transfers/{first['id']}/proceed")
    second = send(180_001)
    second = c.post(f"/api/transfers/{second['id']}/answers", json={"answers": [False] * 3}).json()
    assert second["status"] == "awaiting_family"
    req = c.get("/api/phone/erzhan").json()["family_requests"][0]
    assert "2-я попытка" in req["explanation"] and "360 001" in req["explanation"]


def test_hang_up_then_transfer_reaches_family():
    on_call()
    c.post("/api/director/end_call")
    tr = send(900_000)
    assert tr["status"] == "questions" and "звонок закончился меньше 30 минут назад" in tr["reasons"]
    tr = c.post(f"/api/transfers/{tr['id']}/answers", json={"answers": [False] * 3}).json()
    assert tr["status"] == "awaiting_family"
    assert c.post(f"/api/transfers/{tr['id']}/proceed").status_code == 409
    req = c.get("/api/phone/erzhan").json()["family_requests"][0]
    assert "только что закончила телефонный разговор" in req["explanation"]


def test_warm_up_does_not_whitelist():
    c.post("/api/phone/aigerim/lang/ru")
    assert send(1_000)["status"] == "completed"
    tr = send(900_000)
    assert "новый получатель" in tr["reasons"]
    if tr["status"] == "questions":  # at night (Almaty) the extra NIGHT weight asks the questions first
        tr = c.post(f"/api/transfers/{tr['id']}/answers", json={"answers": [False] * 3}).json()
    assert tr["status"] == "awaiting_family"


def test_yes_answers_go_to_the_bank_not_the_son():
    tr = scam_transfer_to_family(answers=(True, True, True))
    assert tr["status"] == "held"
    son = c.get("/api/phone/erzhan").json()
    assert son["family_requests"] == [] and son["notices"][0]["kind"] == "info"


def test_only_the_guardian_can_decide():
    scam_transfer_to_family()
    rid = c.get("/api/phone/erzhan").json()["family_requests"][0]["id"]
    assert c.post(f"/api/family/requests/{rid}/decision", json={"client_id": "aigerim", "approve": True}).status_code == 403
    assert c.post(f"/api/family/requests/{rid}/decision", json={"client_id": "erzhan", "approve": True}).status_code == 200


def test_complaint_by_number_only_does_not_hold_others():
    r = c.post("/api/complaints", json={"client_id": "madina", "account": SISTER_OF_NOBODY}).json()
    assert not r["confirmed"]
    tr = send(50_000, SISTER_OF_NOBODY, "erzhan")
    assert tr["status"] != "questions" and "по получателю есть непроверенный сигнал" in tr["reasons"]


def test_shield_ignores_long_standing_recipients():
    on_call()
    tr = send(300_000, "KZ55 8562 0000 0128 7740")  # the sister, paid for years: a warning, not the son
    assert tr["status"] == "warning"


def test_fresh_loan_to_a_new_recipient_holds():
    STATE.clients["madina"].loan = (500_000, time.time() - 20 * 3600)
    tr = send(350_000, "KZ99 8562 0000 0555 0001", "madina")
    assert tr["level"] == 2 and "переводится только что полученный кредит" in tr["reasons"]


def test_saved_money_is_counted_once():
    tr = scam_transfer_to_family(answers=(True, False, False))
    c.post(f"/api/transfers/{tr['id']}/cancel")
    assert c.get("/api/stage").json()["saved"] == 900_000


def test_shadow_mode_never_delays_money(monkeypatch):
    monkeypatch.setenv("QAQPAN_SHADOW", "1")
    on_call()
    tr = send(900_000)
    assert tr["status"] == "completed"
    assert any("Теневой режим" in e["text"] for e in c.get("/api/stage").json()["events"])


def test_night_is_almaty_time():
    from datetime import datetime, timezone
    from api.risk import ALMATY
    utc_5am = datetime(2026, 11, 20, 5, 0, tzinfo=timezone.utc).astimezone(ALMATY)
    from api.risk import assess
    from api.state import Account
    a = assess(STATE.clients["madina"], Account("1", "1", "x", "BCC"), 10_000, False, False, 0, utc_5am)
    assert "NIGHT" not in a.reasons


def test_locked_stand_needs_the_key_except_message_check(monkeypatch):
    monkeypatch.setenv("QAQPAN_DIRECTOR_KEY", "s3cret")
    monkeypatch.setenv("QAQPAN_LOCK", "1")
    body = {"client_id": "aigerim", "account": SCAM, "amount": 1000}
    assert c.post("/api/transfers", json=body).status_code == 403
    assert c.post("/api/transfers", json=body, headers={"X-Director-Key": "s3cret"}).status_code == 200
    assert c.post("/api/messages/check", json={"text": "Привет"}).status_code == 200
    assert c.get("/api/phone/aigerim").status_code == 200


def test_public_link_resets_after_idle(monkeypatch):
    monkeypatch.setenv("QAQPAN_IDLE_RESET_MIN", "10")
    c.post("/api/transfers", json={"client_id": "aigerim", "account": SCAM, "amount": 1000})
    for e in STATE.events:
        e.ts -= 11 * 60
    assert c.get("/api/stage").json()["events"][-1]["kind"] == "reset"
    assert c.get("/api/phone/aigerim").json()["transfers"] == []


def test_sandboxes_are_isolated_and_drive_themselves(monkeypatch):
    monkeypatch.setenv("QAQPAN_DIRECTOR_KEY", "s3cret")
    a, b = {"X-Qaqpan-Session": "visitora1"}, {"X-Qaqpan-Session": "visitorb2"}
    assert c.post("/api/director/call", headers=a).status_code == 200  # no presenter key needed in an own sandbox
    assert c.post("/api/director/call").status_code == 403            # the shared stage still needs it
    c.post("/api/phone/aigerim/call/answer", headers=a)
    assert c.get("/api/phone/aigerim", headers=a).json()["call"]["answered"] is True
    assert c.get("/api/phone/aigerim", headers=b).json()["call"] is None
    assert c.get("/api/phone/aigerim").json()["call"] is None
    tr = c.post("/api/transfers", json={"client_id": "aigerim", "account": SCAM, "amount": 900_000}, headers=a).json()
    assert tr["status"] == "questions"
    assert c.get("/api/phone/aigerim", headers=b).json()["transfers"] == []


# ---------------------------------------------------------------- «Отложить на час», получатель, кодовое слово

def warning_transfer():
    """Madina, no shield: a new recipient during a call -> questions -> «no» -> warning."""
    c.post("/api/phone/madina/native-call", json={"on_call": True})
    tr = send(200_000, "KZ99 8562 0000 0555 0002", "madina")
    if tr["status"] == "questions":
        tr = c.post(f"/api/transfers/{tr['id']}/answers", json={"answers": [False] * 3}).json()
    assert tr["status"] == "warning"
    return tr


def test_delay_an_hour_then_qaqpan_concludes_and_the_bank_checks():
    tr = warning_transfer()
    d = c.post(f"/api/transfers/{tr['id']}/delay").json()
    assert d["status"] == "delayed" and d["release_at"] - time.time() > 3500 and "отложен" in d["title"]
    view = c.get("/api/phone/madina").json()["transfers"][-1]
    assert view["analysis"]["verdict"] in ("likely_scam", "unclear") and view["analysis"]["reasons"]
    assert any("звонка" in r for r in view["analysis"]["reasons"])
    assert c.post(f"/api/transfers/{tr['id']}/proceed").status_code == 409  # cannot skip the hour
    c.post("/api/director/skip_hour")
    after = c.get("/api/phone/madina").json()["transfers"][-1]
    if view["analysis"]["verdict"] == "likely_scam":
        assert after["status"] == "held" and "проверит сотрудник банка" in after["message"]
    else:
        assert after["status"] == "completed"


def test_a_delayed_transfer_can_be_cancelled_and_counts_as_saved():
    tr = warning_transfer()
    c.post(f"/api/transfers/{tr['id']}/delay")
    assert c.post(f"/api/transfers/{tr['id']}/cancel").json()["status"] == "cancelled"
    assert c.get("/api/stage").json()["saved"] == 200_000


def test_calm_known_situation_is_released_after_the_hour():
    from api.delay import rules
    v, codes = rules({k: False for k in ("PRESSURE_CALL", "SCAM_MESSAGE_TODAY", "BANK_NOT_CALLING", "NEW_RECIPIENT",
                                          "LARGE_SHARE", "RECIPIENT_REPORTED", "REPEATED_ATTEMPTS", "OWN_OTHER_BANK", "LOAN_FRESH")})
    assert v == "likely_ok" and codes == ["NO_RISK_SIGNS"]


def test_recipient_check_says_only_complaints_or_not():
    scam_transfer_to_family(answers=(True, False, False))
    tr_id = [t for t in STATE.transfers.values() if t.client_id == "aigerim"][-1].id
    c.post("/api/complaints", json={"client_id": "aigerim", "transfer_id": tr_id})
    r = c.post("/api/recipients/check", json={"client_id": "madina", "account": SCAM}).json()
    assert r["status"] == "complaints" and "Данияр" not in r["message"]
    assert c.post("/api/recipients/check", json={"client_id": "madina", "account": "KZ77 0000 1111 2222 3333"}).json()["status"] == "clean"
    assert c.post("/api/recipients/check", json={"client_id": "aigerim", "account": OWN_CARD}).json()["status"] == "own"
    assert "KZ77000011112222" not in "".join(STATE.accounts)  # a check creates no account record


def test_family_code_word_is_suggested_for_the_relative_scheme():
    text = "Мама, это я, у меня новый номер. Срочно нужны деньги, скинь 50 000"
    r = c.post("/api/messages/check", json={"client_id": "aigerim", "text": text, "lang": "ru"}).json()
    assert "Договоритесь" in r["tip"]
    c.post("/api/family/aigerim/codeword", json={"agreed": True})
    assert c.get("/api/phone/erzhan").json()["shield"]["codeword"] is True  # the son shares it
    r = c.post("/api/messages/check", json={"client_id": "aigerim", "text": text, "lang": "ru"}).json()
    assert "кодовое слово" in r["tip"] and "Не знает" in r["tip"]


# ---------------------------------------------------------------- the bank's antifraud console

def full_scenario():
    """Aigerim is stopped under a call, the son declines, she complains; Madina then pays the same account."""
    tr = scam_transfer_to_family()
    rid = c.get("/api/phone/erzhan").json()["family_requests"][0]["id"]
    c.post(f"/api/family/requests/{rid}/decision", json={"client_id": "erzhan", "approve": False})
    c.post("/api/complaints", json={"client_id": "aigerim", "transfer_id": tr["id"]})
    m = send(150_000, SCAM, "madina")
    return c.post(f"/api/transfers/{m['id']}/answers", json={"answers": [True, True, False]}).json()


def test_console_finds_the_drop_account_and_queues_the_stopped_transfer():
    held = full_scenario()
    con = c.get("/api/bank/console").json()
    drop = next(d for d in con["drops"] if "1934" in d["display"])
    assert drop["label"] == "drop" and drop["senders"] == 2 and drop["inflow"] == 1_050_000
    assert any("разных клиентов" in s for s in drop["signals"])
    q = con["queue"][0]
    assert q["id"] == held["id"] and q["status"] == "held" and q["note"]["text"]
    assert con["stats"]["saved"] == 1_050_000 and con["stats"]["drops"] == 1


def test_unusual_amount_for_this_client():
    on_call()
    tr = send(900_000)
    assert any("раз больше ваших обычных трат" in r for r in tr["reasons"])
    item = c.get("/api/bank/console").json()
    assert item is not None


def test_analyst_blocks_and_the_account_is_confirmed_for_everyone():
    on_call()
    tr = send(900_000)
    tr = c.post(f"/api/transfers/{tr['id']}/answers", json={"answers": [True, False, False]}).json()
    assert tr["status"] == "held"
    assert c.post(f"/api/bank/transfers/{tr['id']}/decision", json={"action": "block"}).json()["status"] == "cancelled"
    notice = c.get("/api/phone/aigerim").json()["notices"][-1]
    assert "заблокировал" in notice["body"] or "бұғаттады" in notice["body"]
    m = send(100_000, SCAM, "madina")
    assert m["status"] == "questions" and "жалоб" in m["message"]


def test_analyst_can_release_a_delayed_transfer():
    tr = warning_transfer()
    c.post(f"/api/transfers/{tr['id']}/delay")
    assert c.post(f"/api/bank/transfers/{tr['id']}/decision", json={"action": "release"}).json()["status"] == "completed"
    assert c.post(f"/api/bank/transfers/{tr['id']}/decision", json={"action": "block"}).status_code == 409
