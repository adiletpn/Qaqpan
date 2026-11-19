"""«Спросить Qaqpan» — AI assistant inside the bank app that knows the client's current situation.

The assistant sees what Qaqpan sees (is a call going on, does the bank's own call log show an employee
calling, what was checked today, is a transfer on hold) and answers in plain words, RU or KK.
Guardrails: fraud and safety topics only; never asks for codes or card data; never approves transfers.
Without the AI (no key, network down, limits) a keyword FAQ answers, so the screen is never empty.
"""

from __future__ import annotations

import re
import time

from pydantic import BaseModel

from . import llm
from .state import NATIVE_NUMBER, STATE

SYSTEM = """Ты — «Помощник Qaqpan», модуль защиты от мошенников в приложении банка в Казахстане.
Отвечай на языке клиента ({lang_name}), коротко (2–4 предложения), простыми словами, тепло и уверенно.
Пиши обычным текстом, без markdown, звёздочек и списков.
Темы: мошенничество, звонки «из банка/полиции/eGov», SMS и ссылки, покупки на OLX, переводы, что делать,
если обманули. На другие темы вежливо скажи, что помогаешь только с безопасностью денег.
Жёсткие правила:
- никогда не проси коды из SMS, PIN, CVV, пароли, данные карты;
- не одобряй и не проводи переводы, не обещай вернуть деньги;
- «безопасных счетов» не существует; банк, полиция, eGov никогда не просят переводить деньги;
- при угрозе: положить трубку, позвонить в банк по номеру 505 (сам), в полицию — 102;
- можешь советовать функции приложения: «Проверить сообщение», «Банк мне звонит?», «Семейный щит»,
  «Меня обманули».
Начинай с главного действия. Если в ситуации клиента ниже есть подходящий факт, назови его прямо, это
важнее общих советов: например «Я сверился с журналом банка: сотрудники банка вам сейчас не звонят» или
«Ваш перевод на паузе — деньги на месте».
Ситуация клиента прямо сейчас:
{context}"""


class AssistantReply(BaseModel):
    reply: str
    source: str


def context_for(cid: str, lang: str) -> str:
    c = STATE.clients[cid]
    lines = []
    call = STATE.calls.get(cid)
    if call and call.answered:
        if cid in STATE.bank_outbound:
            emp = STATE.bank_outbound[cid]
            lines.append(f"- идёт звонок, и это действительно сотрудник банка: {emp.employee}, {emp.department}")
        else:
            src = "номер неизвестен" if call.number == NATIVE_NUMBER else f"номер {call.number}"
            lines.append(f"- у клиента идёт телефонный звонок ({src}); по журналу банка сотрудники банка ему сейчас НЕ звонят")
    since = time.time() - 3 * 3600
    for a in STATE.alerts.get(cid, []):
        if a.ts >= since:
            lines.append(f"- сегодня: {a.text['ru']}")
    held = [t for t in STATE.transfers.values() if t.client_id == cid and t.status in ("questions", "held", "awaiting_family", "escalated")]
    for t in held[-1:]:
        lines.append(f"- перевод {t.amount:,.0f} ₸ сейчас на паузе (Qaqpan заподозрил обман)".replace(",", " "))
    link = STATE.link_for_ward(cid)
    if link:
        lines.append(f"- доверенное лицо в семейном щите: {STATE.clients[link.guardian_id].short} ({link.guardian_title['ru']})")
    lines.append(f"- имя клиента: {c.short}")
    return "\n".join(lines)


# ---------------------------------------------------------------- offline answers

FAQ = [
    (r"банк|служб\w* безопасн|полици|мвд|кнб|следовател|звон|банкт|полиция|қоңырау",
     {"ru": "Сотрудники банка и полиции никогда не просят переводить деньги, называть коды или ставить приложения. "
            "Положите трубку и сами позвоните в банк по номеру 505. Во время звонка нажмите «Банк мне звонит?» — я сверю с журналом банка.",
      "kk": "Банк пен полиция қызметкерлері ешқашан ақша аударуды, код айтуды немесе қосымша орнатуды сұрамайды. "
            "Телефонды қойып, банкке 505 нөміріне өзіңіз қоңырау шалыңыз. Қоңырау кезінде «Банк қоңырау шалып тұр ма?» түймесін басыңыз."}),
    (r"безопасн\w* сч|қауіпсіз шот|спасти|сақта",
     {"ru": "«Безопасных счетов» не бывает — это главная фраза мошенников. Ничего не переводите и положите трубку.",
      "kk": "«Қауіпсіз шот» деген болмайды — бұл алаяқтардың басты сөзі. Ештеңе аудармаңыз, телефонды қойыңыз."}),
    (r"эцп|эцқ|egov|цон|хқко",
     {"ru": "ЭЦП продлевают только на egov.kz или в ЦОНе, по SMS-ссылкам — никогда. Не переходите по ссылке; "
            "если сомневаетесь — проверьте сообщение кнопкой «Проверить сообщение».",
      "kk": "ЭЦҚ тек egov.kz сайтында немесе ХҚКО-да ұзартылады, SMS-сілтеме арқылы — ешқашан. Сілтемеге өтпеңіз."}),
    (r"olx|предоплат|доставк|продав|купить|покуп|алдын ала|сатушы",
     {"ru": "Не платите предоплату незнакомому продавцу и не переходите по ссылкам «оплаты доставки». "
            "Безопаснее встретиться лично или платить при получении.",
      "kk": "Бейтаныс сатушыға алдын ала төлемеңіз, «жеткізу ақысы» сілтемелеріне өтпеңіз. Тауарды алған кезде төлеген қауіпсіз."}),
    (r"обманул|перевел|перевёл|украл|похитил|алдады|аударып қойдым",
     {"ru": "Сразу позвоните в банк по номеру 505 и попросите остановить перевод, затем подайте заявление в полицию (102). "
            "На экране «Меня обманули» готово заявление — откройте его.",
      "kk": "Дереу 505 нөміріне банкке қоңырау шалып, аударымды тоқтатуды сұраңыз, содан кейін полицияға (102) өтініш беріңіз."}),
    (r"код|пароль|cvv|pin|пин|кодты",
     {"ru": "Никому не сообщайте коды из SMS, PIN и CVV — даже «сотрудникам банка». Настоящий банк их не спрашивает.",
      "kk": "SMS-кодтарды, PIN мен CVV-ны ешкімге айтпаңыз — «банк қызметкеріне» де. Нағыз банк оларды сұрамайды."}),
]
DEFAULT = {"ru": "Я помогу понять, не мошенники ли это. Опишите, что происходит: кто пишет или звонит и что просят.",
           "kk": "Бұл алаяқтар ма, жоқ па — түсінуге көмектесемін. Не болып жатқанын жазыңыз: кім жазады не қоңырау шалады және не сұрайды."}


def offline_reply(cid: str, text: str, lang: str) -> str:
    call = STATE.calls.get(cid)
    prefix = ""
    if call and call.answered and cid not in STATE.bank_outbound:
        prefix = ("Вижу, что вам сейчас звонят, а банк вам не звонит — если собеседник назвался банком, это мошенник. "
                  if lang == "ru" else "Сізге қазір қоңырау шалып жатыр, ал банк қоңырау шалмайды — әңгімелесуші өзін банк деп атаса, ол алаяқ. ")
    low = text.lower()
    for pattern, answer in FAQ:
        if re.search(pattern, low):
            return prefix + answer[lang]
    return prefix + DEFAULT[lang]


def answer(cid: str, history: list[dict], lang: str) -> AssistantReply:
    last = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    system = SYSTEM.format(lang_name="казахский" if lang == "kk" else "русский", context=context_for(cid, lang))
    payload = {"system": system, "history": history[-8:]}
    reply, source = llm.cached_call("assistant", payload, AssistantReply,
                                    lambda: _live(system, history[-8:]), allow_in_demo=True)
    if reply:
        return reply.model_copy(update={"source": source})
    return AssistantReply(reply=offline_reply(cid, last, lang), source="offline")


def _live(system: str, history: list[dict]) -> AssistantReply | None:
    text = llm.chat(system, history, max_tokens=400)
    if not text or not text.strip():
        return None
    clean = re.sub(r"^#+\s*", "", text.strip(), flags=re.M)  # headings are useless in a chat bubble
    return AssistantReply(reply=clean, source="llm")
