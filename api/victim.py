"""Layer «Если всё же обманули»: ready-made statement + step-by-step instructions.

The statement is a draft the victim reviews before submitting, so free LLM text is allowed here.
Without the model a template is used — the feature never fails.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from . import llm
from .texts import Lang

STEPS: dict[str, list[str]] = {
    "ru": [
        "Сразу позвоните в банк по номеру 505: заблокируйте карту и попросите остановить перевод через Антифрод-центр.",
        "Подайте заявление в полицию (102 или в ближайшем отделении) — текст ниже уже готов.",
        "Сохраните скриншоты переписки, номер звонившего и чек перевода.",
        "Не перезванивайте мошенникам и не платите «за возврат денег» — это вторая волна обмана.",
    ],
    "kk": [
        "Дереу 505 нөміріне банкке қоңырау шалыңыз: картаны бұғаттап, Антифрод-орталық арқылы аударымды тоқтатуды сұраңыз.",
        "Полицияға өтініш беріңіз (102 немесе жақын бөлімше) — мәтін төменде дайын.",
        "Хат алмасу скриншоттарын, қоңырау шалушының нөмірін және аударым чегін сақтаңыз.",
        "Алаяқтарға қайта қоңырау шалмаңыз және «ақшаны қайтару үшін» төлемеңіз — бұл алаяқтықтың екінші толқыны.",
    ],
}


class Statement(BaseModel):
    title: str
    body: str = Field(description="Full statement text, formal, ready to submit")


class VictimHelp(BaseModel):
    steps: list[str]
    statement: Statement
    source: str


def _template(lang: Lang, name: str, amount: float | None, account: str | None, phone: str | None, scheme: str) -> Statement:
    date = datetime.now().strftime("%d.%m.%Y")
    amt = f"{amount:,.0f} ₸".replace(",", " ") if amount else "[сумма]"
    if lang == "kk":
        body = (f"Мен, {name}, {date} алаяқтық әрекеттердің құрбаны болдым.\n\n"
                f"Маған {phone or '[нөмір]'} нөмірінен қоңырау шалып, өздерін {scheme} қызметкері деп таныстырды. "
                f"Олардың қысымымен мен {account or '[шот]'} шотына {amt} аудардым.\n\n"
                "Қылмыстық іс қозғауды, аударым алушының шотын бұғаттауды және ақшаны қайтаруға жәрдемдесуді сұраймын.\n\n"
                "Қосымша: скриншоттар, аударым чегі.")
        return Statement(title="Полиция бөліміне өтініш", body=body)
    body = (f"Я, {name}, {date} стал(а) жертвой мошеннических действий.\n\n"
            f"Мне позвонили с номера {phone or '[номер]'}, звонившие представились сотрудниками {scheme}. "
            f"Под их давлением я перевел(а) {amt} на счёт {account or '[счёт]'}.\n\n"
            "Прошу возбудить уголовное дело, заблокировать счёт получателя и содействовать возврату средств.\n\n"
            "Приложения: скриншоты переписки, чек перевода.")
    return Statement(title="Заявление в отдел полиции", body=body)


STATEMENT_EXAMPLE = '{"title": "Заявление в отдел полиции", "body": "полный текст заявления"}'

SYSTEM = """Ты помогаешь жертве финансового мошенничества в Казахстане составить заявление в полицию.
Пиши официально, кратко, на языке {lang_name}, от первого лица. Используй только данные из запроса,
недостающее помечай в квадратных скобках. Не добавляй статьи закона и номера, которых нет во входных данных."""


def build(lang: Lang, name: str, amount: float | None, account: str | None, phone: str | None,
          scheme: str, story: str | None) -> VictimHelp:
    fallback = _template(lang, name, amount, account, phone, scheme)
    if story:
        payload = {"lang": lang, "name": name, "amount": amount, "account": account, "phone": phone, "scheme": scheme, "story": story}
        prompt = "Данные пострадавшего:\n" + "\n".join(f"{k}: {v}" for k, v in payload.items() if v)
        system = SYSTEM.format(lang_name="казахском" if lang == "kk" else "русском")
        result, source = llm.cached_call("statement", payload, Statement,
                                         lambda: llm.parse(system, prompt, Statement, STATEMENT_EXAMPLE, max_tokens=1500))
        if result:
            return VictimHelp(steps=STEPS[lang], statement=result, source=source)
    return VictimHelp(steps=STEPS[lang], statement=fallback, source="template")
