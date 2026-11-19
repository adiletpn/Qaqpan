"""The AI layer must never take a feature down: no credentials -> rules / templates."""

import pytest

from api import llm, msgcheck, victim


@pytest.fixture
def no_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("QAQPAN_DEMO", raising=False)
    monkeypatch.delenv("XKIRO_API_KEY", raising=False)  # no key at all
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "_disabled_reason", None)
    yield
    monkeypatch.setattr(llm, "_disabled_reason", None)


def test_message_check_falls_back_to_rules(no_credentials):
    r = msgcheck.check("Срочно переведите деньги на безопасный счёт", None, "image/png", None, "ru")
    assert r.source == "rules" and r.verdict == "scam"
    assert llm.status()["key"] is False


def test_statement_falls_back_to_template(no_credentials):
    h = victim.build("ru", "Айгерим Сейткали", 900_000, "KZ86", "+7 727", "полиции", story="звонили из полиции")
    assert h.source == "template" and "900 000" in h.statement.body


def test_demo_mode_never_calls_the_model(monkeypatch, tmp_path):
    monkeypatch.setenv("QAQPAN_DEMO", "1")
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("XKIRO_API_KEY", "sk-test")
    monkeypatch.setattr(llm, "_post", lambda body: (_ for _ in ()).throw(AssertionError("live call in demo mode")))
    assert msgcheck.check("Вы выиграли приз", None, "image/png", None, "ru").source == "rules"


def test_gateway_error_falls_back_to_rules(monkeypatch, tmp_path):
    monkeypatch.delenv("QAQPAN_DEMO", raising=False)
    monkeypatch.setenv("XKIRO_API_KEY", "sk-test")
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "_disabled_reason", None)

    def down(body):
        raise llm.Unavailable("HTTP 502")

    monkeypatch.setattr(llm, "_post", down)
    assert msgcheck.check("Срочно скинь деньги, мама", None, "image/png", None, "ru").source == "rules"


def test_ai_never_softens_a_confident_rules_verdict(monkeypatch, tmp_path):
    monkeypatch.delenv("QAQPAN_DEMO", raising=False)
    monkeypatch.setenv("XKIRO_API_KEY", "sk-test")
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "_disabled_reason", None)
    fake = {"choices": [{"finish_reason": "stop", "message": {"content":
            '{"verdict": "safe", "confidence": 0.7, "scheme": "none", "reasons": ["выглядит нормально"], '
            '"advice": "всё хорошо", "extracted_text": "x"}'}}]}
    monkeypatch.setattr(llm, "_post", lambda body: fake)
    r = msgcheck.check("Переведите деньги на безопасный счёт, это служба безопасности", None, "image/png", None, "ru")
    assert r.source == "llm" and r.verdict == "scam"
    assert r.reasons[0].code != "LLM"  # curated rule reason comes first
