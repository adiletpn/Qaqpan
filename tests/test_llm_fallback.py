"""The AI layer must never take a feature down: no credentials -> rules / templates."""

import pytest

from api import llm, msgcheck, victim


@pytest.fixture
def no_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("QAQPAN_DEMO", raising=False)
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "_disabled_reason", None)

    def boom():
        raise TypeError("Could not resolve authentication method")

    monkeypatch.setattr(llm, "_get_client", boom)
    yield
    monkeypatch.setattr(llm, "_disabled_reason", None)


def test_message_check_falls_back_to_rules(no_credentials):
    r = msgcheck.check("Срочно переведите деньги на безопасный счёт", None, "image/png", None, "ru")
    assert r.source == "rules" and r.verdict == "scam"
    assert llm.status()["live_disabled"]


def test_statement_falls_back_to_template(no_credentials):
    h = victim.build("ru", "Айгерим Сейткали", 900_000, "KZ86", "+7 727", "полиции", story="звонили из полиции")
    assert h.source == "template" and "900 000" in h.statement.body


def test_demo_mode_never_calls_the_model(monkeypatch, tmp_path):
    monkeypatch.setenv("QAQPAN_DEMO", "1")
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "_get_client", lambda: (_ for _ in ()).throw(AssertionError("live call in demo mode")))
    assert msgcheck.check("Вы выиграли приз", None, "image/png", None, "ru").source == "rules"
