"""Layer «Если всё же обманули»: ready-made statement + step-by-step instructions.

The statement is a draft the victim reviews before submitting, so free LLM text is allowed here.
Without the model a template is used — the feature never fails.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from . import llm
from .risk import local_now
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


ATTEMPT_STEPS: dict[str, list[str]] = {
    "ru": [
        "Деньги на вашем счёте: перевод остановлен. Не перезванивайте на номер, с которого звонили.",
        "Если вы называли коды или устанавливали приложение — позвоните в банк по номеру 505 и смените пароль.",
        "Подайте заявление о попытке мошенничества (102 или e-Otinish) — текст ниже уже готов. Так номер и счёт проверят.",
        "Расскажите близким: следующей могут позвонить им.",
    ],
    "kk": [
        "Ақшаңыз шотыңызда: аударым тоқтатылды. Қоңырау шалған нөмірге қайта хабарласпаңыз.",
        "Кодтарды айтсаңыз немесе қосымша орнатсаңыз — 505 нөміріне банкке қоңырау шалып, құпиясөзді ауыстырыңыз.",
        "Алаяқтық әрекеті туралы өтініш беріңіз (102 немесе e-Otinish) — мәтін төменде дайын. Нөмір мен шот тексеріледі.",
        "Жақындарыңызға айтыңыз: келесі қоңырау соларға болуы мүмкін.",
    ],
}


class Statement(BaseModel):
    title: str
    body: str = Field(description="Full statement text, formal, ready to submit")


class VictimHelp(BaseModel):
    steps: list[str]
    statement: Statement
    source: str


def _attempt(lang: Lang, name: str, date: str, amt: str, account: str | None, phone: str | None, scheme: str) -> Statement:
    """The transfer was stopped: the money is safe, but the attempt is still worth reporting (the account, the number)."""
    if lang == "kk":
        body = (f"Мен, {name}, {date} маған қатысты алаяқтық әрекет жасалғаны туралы хабарлаймын.\n\n"
                f"Маған {phone or '[нөмір]'} нөмірінен қоңырау шалып, өздерін {scheme} қызметкері деп таныстырды және "
                f"{account or '[шот]'} шотына {amt} аударуға көндірді. Аударымды банк тоқтатты, ақша менің шотымда қалды.\n\n"
                "Осы нөмір мен шоттың иелерін тексеріп, алаяқтарды жауапкершілікке тартуды сұраймын.\n\n"
                "Қосымша: қоңыраулар тізімінің скриншоты.")
        return Statement(title="Алаяқтық әрекеті туралы өтініш", body=body)
    body = (f"Я, {name}, {date} сообщаю о попытке мошенничества в отношении меня.\n\n"
            f"Мне позвонили с номера {phone or '[номер]'}, звонившие представились сотрудниками {scheme} и убеждали "
            f"перевести {amt} на счёт {account or '[счёт]'}. Перевод остановил банк, деньги остались на моём счёте.\n\n"
            "Прошу проверить владельцев номера и счёта и привлечь мошенников к ответственности.\n\n"
            "Приложения: скриншот списка вызовов.")
    return Statement(title="Заявление о попытке мошенничества", body=body)


def _template(lang: Lang, name: str, amount: float | None, account: str | None, phone: str | None, scheme: str,
              attempt: bool = False) -> Statement:
    date = local_now().strftime("%d.%m.%Y")
    amt = f"{amount:,.0f} ₸".replace(",", " ") if amount else "[сумма]"
    if attempt:
        return _attempt(lang, name, date, amt, account, phone, scheme)
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
          scheme: str, story: str | None, attempt: bool = False) -> VictimHelp:
    fallback = _template(lang, name, amount, account, phone, scheme, attempt)
    if story:
        payload = {"lang": lang, "name": name, "amount": amount, "account": account, "phone": phone, "scheme": scheme, "story": story,
                   **({"outcome": "перевод остановлен банком, деньги не ушли"} if attempt else {})}
        prompt = "Данные пострадавшего:\n" + "\n".join(f"{k}: {v}" for k, v in payload.items() if v)
        system = SYSTEM.format(lang_name="казахском" if lang == "kk" else "русском")
        result, source = llm.cached_call("statement", payload, Statement,
                                         lambda: llm.parse(system, prompt, Statement, STATEMENT_EXAMPLE, max_tokens=1500))
        if result:
            return VictimHelp(steps=(ATTEMPT_STEPS if attempt else STEPS)[lang], statement=result, source=source)
    return VictimHelp(steps=(ATTEMPT_STEPS if attempt else STEPS)[lang], statement=fallback, source="template")
