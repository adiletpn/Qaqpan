"""Message rules: every demo sample and the main Kazakhstan schemes, RU and KK."""

import json
from pathlib import Path

import pytest

from api.msgcheck import check_rules

SAMPLES = json.loads((Path(__file__).resolve().parent.parent / "data" / "samples.json").read_text())


@pytest.mark.parametrize("sample", SAMPLES, ids=[s["id"] for s in SAMPLES])
def test_demo_samples(sample):
    verdict = check_rules(sample["text"], "ru").verdict
    expected = "safe" if sample["id"].startswith("legit") else "scam"
    assert verdict == expected


@pytest.mark.parametrize("text,scheme", [
    ("Переведите все сбережения на безопасный счёт, это следователь", "safe_account"),
    ("ЭЦП истекает, продлите по ссылке egov-kz.top", "ecp_egov"),
    ("Сдай карту в аренду, 5 000 тг в день", "drop_recruit"),
    ("Скачайте AnyDesk для возврата средств", "remote_app"),
    ("Вы выиграли приз! Оплатите доставку", "prize"),
])
def test_scheme_detected(text, scheme):
    r = check_rules(text, "ru")
    assert r.verdict != "safe" and r.scheme == scheme


def test_kazakh_reasons_are_kazakh():
    r = check_rules("Ақшаңызды қауіпсіз шотқа аударыңыз", "kk")
    assert r.verdict == "scam"
    assert "шот" in r.reasons[0].text


def test_official_domain_is_not_flagged():
    assert check_rules("Результат услуги в личном кабинете egov.kz", "ru").verdict == "safe"


def test_lookalike_domain_is_flagged():
    r = check_rules("Подробнее: egov-kz.online/info", "ru")
    assert any(x.code == "LINK_LOOKALIKE" for x in r.reasons)


def test_otp_warning_is_not_a_code_request():
    r = check_rules("Код: 1234. Никому не сообщайте код", "ru")
    assert r.verdict == "safe"
