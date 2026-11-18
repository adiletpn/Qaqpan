"""Transfer risk scoring: levels and reason codes."""

from datetime import datetime

from api.risk import assess
from api.state import Account, Client

DAY = datetime(2026, 11, 20, 14, 0)
NIGHT = datetime(2026, 11, 20, 3, 0)


def client(balance=1_000_000):
    return Client("c", "Тест Т.", "Тест", 40, "Алматы", "ru", balance, "+7 700 000 00 00", known_accounts={"111", "777"})


def acc(number="999", **kw):
    return Account(number, number, "Получатель", "BCC", **kw)


def test_known_small_transfer_passes():
    a = assess(client(), acc("111"), 20_000, False, False, 0, DAY)
    assert a.level == 0 and "KNOWN_RECIPIENT" in a.reasons


def test_new_recipient_alone_is_not_blocked():
    assert assess(client(), acc(), 20_000, False, False, 0, DAY).level == 0


def test_call_plus_big_share_holds():
    a = assess(client(), acc(), 700_000, True, False, 0, DAY)
    assert a.level == 2 and a.template == "call"
    assert {"CALL_ACTIVE", "NEW_RECIPIENT", "BIG_SHARE", "BIG_AMOUNT"} <= set(a.reasons)
    assert a.kw["pct"] == 70


def test_complaints_hold_even_without_call():
    a = assess(client(), acc(complaints=1), 50_000, False, False, 0, DAY)
    assert a.level == 2 and a.template == "purchase"


def test_afc_listed_account_holds():
    assert assess(client(), acc(in_afc=True), 10_000, False, False, 0, DAY).level == 2


def test_behaviour_signals_add_up_to_a_warning():
    a = assess(client(), acc(), 100_000, False, True, 3, NIGHT)
    assert a.level == 1 and {"NIGHT", "PASTED", "APP_SWITCH"} <= set(a.reasons)


def test_score_is_clipped():
    a = assess(client(balance=100_000), acc(complaints=2, in_afc=True), 95_000, True, True, 5, NIGHT)
    assert a.score == 1.0


def test_known_recipient_gets_no_discount_during_a_call():
    a = assess(client(), acc("111"), 600_000, True, False, 0, DAY)
    assert "KNOWN_RECIPIENT" not in a.reasons and a.level == 2


def test_own_card_in_other_bank_during_call_is_flagged():
    own = Account("777", "777", "Своя карта", "Другой банк", owner_id="c")
    a = assess(client(), own, 800_000, True, False, 0, DAY)
    assert "OWN_OTHER_BANK" in a.reasons and a.level == 2
    calm = assess(client(), own, 800_000, False, False, 0, DAY)
    assert "OWN_OTHER_BANK" not in calm.reasons and calm.level == 0
