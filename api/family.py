"""Family shield: what the guardian sees and how the link is managed.

Design rules:
  * the guardian is at work and reads this in 3 seconds — plain words, not risk codes;
  * the timeline shows only what Qaqpan knows (checked messages, the fact of a call, call checks,
    the transfer), never the content of calls or SMS the client did not check;
  * no answer in 15 minutes -> a bank employee calls the ward (never auto-approve, never block forever);
  * disabling the shield takes 24 hours and the guardian is notified — a scammer cannot say «turn it off».
"""

from __future__ import annotations

import time

from . import tgbot
from .state import SHIELD_DISABLE_DELAY_S, STATE, FamilyLink, FamilyRequest, Transfer

Lang = str


def _fmt(amount: float) -> str:
    return f"{amount:,.0f} ₸".replace(",", " ")


def _call_minutes(cid: str) -> int:
    call = STATE.calls.get(cid)
    return int((time.time() - call.started) // 60) if call and call.answered else 0


def _session(cid: str, tr: Transfer) -> tuple[int, float]:
    """Attempts to new recipients in the last 24 h (this one included) and their total, cancelled ones excluded."""
    now = time.time()
    mine = [x for x in STATE.transfers.values() if x.client_id == cid and now - x.ts < 24 * 3600
            and not STATE.is_known(cid, x.account, now) and x.ts <= tr.ts]
    return len(mine), sum(x.amount for x in mine if x.status != "cancelled")


def _share(pct: int | None, lang: Lang) -> str:
    # never an exact percentage: with the amount it would reveal the ward's balance
    if not pct:
        return ""
    if lang == "kk":
        return " (шоттағы ақшаның барлығы дерлік)" if pct >= 80 else " (шоттағы ақшаның жартысынан көбі)"
    return " — почти все деньги на счёте" if pct >= 80 else " — больше половины денег на счёте"


def request_view(fr: FamilyRequest, lang: Lang) -> dict:
    tr: Transfer = STATE.transfers[fr.transfer_id]
    link: FamilyLink = STATE.links[fr.from_client]
    ward = STATE.clients[fr.from_client]
    acc = STATE.accounts[tr.account]
    r = set(tr.reasons)
    on_call = "CALL_ACTIVE" in r
    after_call = "RECENT_CALL" in r
    minutes = _call_minutes(ward.id)
    attempts, total = _session(ward.id, tr)
    pct = tr.reason_kw.get("pct")
    amount = _fmt(tr.amount)
    title, dat = link.ward_title[lang], link.ward_title_dat[lang]
    said_yes = bool(tr.answers and any(tr.answers))
    coached = bool(tr.answers is not None and not any(tr.answers) and (on_call or after_call))

    if lang == "kk":
        headline = f"{link.ward_title_acc['kk']} алаяқтар алдап жатуы мүмкін"
        recipient = ("басқа клиенттер шағымданған шотқа" if "RECIPIENT_COMPLAINTS" in r else
                     "басқа банктегі өз картасына — бұл схеманың жиі алғашқы қадамы" if "OWN_OTHER_BANK" in r else
                     "жаңа алушыға" if "NEW_RECIPIENT" in r else "")
        share = _share(pct, "kk")
        if on_call:
            dur = f" ({minutes} минуттан бері)" if minutes >= 1 else ""
            explanation = (f"{title} қазір телефонмен сөйлесіп отыр{dur} және бір мезгілде {recipient} {amount}{share} "
                           "аударып жатыр. Банк немесе полиция атынан қоңырау шалатын алаяқтар осылай әрекет етеді.")
        elif after_call:
            explanation = (f"{title} жақында ғана телефон әңгімесін аяқтады және енді {recipient} {amount}{share} аударып "
                           "жатыр. Алаяқтар жиі «телефонды қойып, өзіңіз аударыңыз» дейді.")
        else:
            explanation = f"{title} {recipient} {amount}{share} аударып жатыр."
        if attempts >= 2:
            explanation += f" Бұл бүгінгі {attempts}-ші аударым әрекеті, барлығы {_fmt(total)}: алаяқтар соманы бөліп аудартады."
        if said_yes:
            explanation += " Qaqpan сұрақтарына берілген жауаптарда қысым белгілері бар: қоңырау шалып, ақша аударуды сұрайды."
        elif coached:
            explanation += (" Qaqpan сұрақтарына жауап — «жоқ», бірақ қоңырау жалғасуда: алаяқтар жиі не деп жауап беру "
                            "керектігін айтып отырады.")
        advice = (f"{dat.capitalize()} әдеттегі нөміріне қоңырау шалып, телефонды қоюын сұраңыз. Сіздің жауабыңызсыз ақша "
                  f"кетпейді. 15 минут ішінде жауап бермесеңіз, аударымды банктің антифрод-талдаушысы тексереді.")
    else:
        headline = f"{link.ward_title_acc['ru']}, возможно, обманывают мошенники"
        recipient = ("на счёт, на который жаловались другие клиенты" if "RECIPIENT_COMPLAINTS" in r else
                     "на свою карту в другом банке — это частый первый шаг схемы" if "OWN_OTHER_BANK" in r else
                     "новому получателю" if "NEW_RECIPIENT" in r else "")
        share = _share(pct, "ru")
        if on_call:
            dur = f" уже {minutes} мин" if minutes >= 1 else ""
            explanation = (f"{title} сейчас говорит по телефону{dur} и одновременно переводит {amount}{share} {recipient}. "
                           "Так действуют мошенники, которые звонят от имени банка или полиции.")
        elif after_call:
            explanation = (f"{title} только что закончила телефонный разговор и теперь переводит {amount}{share} {recipient}. "
                           "Мошенники часто говорят: «положите трубку и переведите сами».")
        else:
            explanation = f"{title} переводит {amount}{share} {recipient}."
        if attempts >= 2:
            explanation += (f" Это {attempts}-я попытка перевода за сутки, всего {_fmt(total)}: мошенники просят "
                            "разбить сумму на части.")
        if said_yes:
            explanation += " В ответах на вопросы Qaqpan есть признаки давления: звонят и просят перевести деньги."
        elif coached:
            explanation += (" На вопросы Qaqpan ответ — «нет», но звонок продолжается: мошенники часто подсказывают, "
                            "что отвечать.")
        advice = (f"Позвоните {dat} на обычный номер и попросите положить трубку. Без вашего ответа деньги не уйдут. "
                  "Если не ответите за 15 минут, перевод проверит антифрод-аналитик банка.")

    since = time.time() - 3 * 3600
    timeline = [{"ts": a.ts, "text": a.text[lang]} for a in STATE.alerts[ward.id] if a.ts >= since]
    return {
        "id": fr.id, "ward_name": ward.short, "ward_title": title, "ward_phone": ward.phone,
        "amount": tr.amount, "account": acc.display, "holder": acc.holder,
        "headline": headline, "explanation": " ".join(explanation.split()), "advice": advice,
        "timeline": timeline, "expires_in": max(0, int(fr.expires - time.time())),
    }


def notify_request(fr: FamilyRequest) -> None:
    link = STATE.links[fr.from_client]
    amount = _fmt(STATE.transfers[fr.transfer_id].amount)
    STATE.notify(fr.guardian_id, "family_request",
                 {"ru": "Qaqpan · Семейный щит", "kk": "Qaqpan · Отбасылық қалқан"},
                 {"ru": f"{link.ward_title_acc['ru']}, возможно, обманывают. Перевод {amount} остановлен до вашего решения",
                  "kk": f"{link.ward_title_acc['kk']} алаяқтар алдауы мүмкін. {amount} аударым сіздің шешіміңізге дейін тоқтатылды"},
                 ref=fr.id)
    tgbot.push_family_request(request_view(fr, "ru"))  # the son's real Telegram, when linked in the demo


def notify_confirmed(ward_id: str, tr: Transfer) -> None:
    """The ward said «yes» to the pressure questions: the bank holds the transfer, the guardian only gets informed."""
    link = STATE.links[ward_id]
    amount = _fmt(tr.amount)
    STATE.notify(link.guardian_id, "info",
                 {"ru": "Qaqpan · Семейный щит", "kk": "Qaqpan · Отбасылық қалқан"},
                 {"ru": f"{link.ward_title['ru']} подтвердила признаки давления. Перевод {amount} остановлен, им занимается "
                        f"банк. Позвоните {link.ward_title_dat['ru']} на обычный номер.",
                  "kk": f"{link.ward_title['kk']} қысым белгілерін растады. {amount} аударым тоқтатылды, оны банк "
                        f"тексереді. {link.ward_title_dat['kk'].capitalize()} әдеттегі нөміріне қоңырау шалыңыз."},
                 ref=tr.id)
    tgbot.push_text(f"{link.ward_title['ru']} подтвердила признаки давления. Перевод {amount} остановлен, им занимается банк. "
                    f"Позвоните {link.ward_title_dat['ru']} на обычный номер.")


def shield_info(cid: str, lang: Lang) -> dict:
    now = time.time()
    codeword = cid in STATE.codewords
    link = STATE.links.get(cid)
    if link:
        g = STATE.clients[link.guardian_id]
        return {"role": "ward", "guardian_name": g.short, "guardian_title": link.guardian_title[lang],
                "limit": link.limit, "active": link.active(now), "codeword": codeword,
                "disable_at": link.disable_at if link.disable_at and link.active(now) else None}
    wards = [{"ward_id": lk.ward_id, "name": STATE.clients[lk.ward_id].short, "title": lk.ward_title[lang],
              "limit": lk.limit, "active": lk.active(now), "disable_at": lk.disable_at if lk.active(now) else None}
             for lk in STATE.links_for_guardian(cid)]
    return {"role": "guardian", "wards": wards, "codeword": codeword} if wards else {"role": "none", "codeword": codeword}


def notify_delayed(ward_id: str, tr: Transfer) -> None:
    link = STATE.links[ward_id]
    amount = _fmt(tr.amount)
    STATE.notify(link.guardian_id, "info", {"ru": "Qaqpan · Семейный щит", "kk": "Qaqpan · Отбасылық қалқан"},
                 {"ru": f"{link.ward_title['ru']} отложила перевод {amount} на час — Qaqpan засомневался. Можно позвонить "
                        f"{link.ward_title_dat['ru']} и спокойно обсудить.",
                  "kk": f"{link.ward_title['kk']} {amount} аударымды бір сағатқа қалдырды — Qaqpan күмәнданды. "
                        f"{link.ward_title_dat['kk'].capitalize()} қоңырау шалып, асықпай сөйлесуге болады."},
                 ref=tr.id)
    tgbot.push_text(f"{link.ward_title['ru']} отложила перевод {amount} на час — Qaqpan засомневался. Можно позвонить "
                    f"{link.ward_title_dat['ru']} и спокойно обсудить.")


def request_disable(ward_id: str) -> FamilyLink:
    link = STATE.links[ward_id]
    if link.disable_at is None:
        link.disable_at = time.time() + SHIELD_DISABLE_DELAY_S
        ward = STATE.clients[ward_id]
        STATE.notify(link.guardian_id, "shield_disable",
                     {"ru": "Qaqpan · Семейный щит", "kk": "Qaqpan · Отбасылық қалқан"},
                     {"ru": f"{link.ward_title['ru']} отключает семейный щит — он выключится через 24 часа. "
                            f"Если об этом просил незнакомец по телефону, позвоните {link.ward_title_dat['ru']}.",
                      "kk": f"{link.ward_title['kk']} отбасылық қалқанды өшіріп жатыр — ол 24 сағаттан кейін өшеді. "
                            f"Мұны телефонмен бейтаныс адам сұраса, {link.ward_title_dat['kk']} қоңырау шалыңыз."},
                     ref=ward_id)
        tgbot.push_text(f"{link.ward_title['ru']} отключает семейный щит — он выключится через 24 часа. Если об этом "
                        f"просил незнакомец по телефону, позвоните {link.ward_title_dat['ru']}.")
        STATE.alert(ward_id, "Запрос на отключение семейного щита", "Отбасылық қалқанды өшіру сұрауы")
        STATE.emit("shield", ward_id, f"{ward.short} отключает щит — выключится только через 24 часа, "
                   f"{STATE.clients[link.guardian_id].short} получил(а) уведомление")
    return link


def keep(ward_id: str) -> FamilyLink:
    link = STATE.links[ward_id]
    if link.disable_at is not None:
        link.disable_at = None
        STATE.emit("shield", ward_id, f"Семейный щит {STATE.clients[ward_id].short} остаётся включённым")
    return link
