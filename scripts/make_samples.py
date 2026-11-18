"""Render demo SMS screenshots -> web/public/samples/*.png and data/samples.json.

These are CONSTRUCTED examples modelled on schemes reported in Kazakhstan news (see `based_on`);
they are not real messages. Run once; outputs are committed.
"""

import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_IMG = ROOT / "web" / "public" / "samples"
OUT_JSON = ROOT / "data" / "samples.json"
FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

SAMPLES = [
    {"id": "ecp", "sender": "eGov", "time": "10:42", "label": {"ru": "SMS «ЭЦП истекает»", "kk": "SMS «ЭЦҚ мерзімі бітеді»"},
     "text": "Уважаемый пользователь! Срок действия вашей ЭЦП истекает сегодня. Во избежание блокировки доступа "
             "к госуслугам продлите ЭЦП по ссылке: egov-kz.online/ecp",
     "based_on": "https://bes.media/news/prodlite-etsp-novaya-shema-moshennichestva-poyavilas-v-kazahstane/"},
    {"id": "ecp_kk", "sender": "eGov", "time": "10:42", "label": {"ru": "SMS «ЭЦҚ» (каз.)", "kk": "SMS «ЭЦҚ»"},
     "text": "Құрметті пайдаланушы! Сіздің ЭЦҚ мерзімі бүгін аяқталады. Мемлекеттік қызметтерге қолжетімділік "
             "бұғатталмас үшін сілтеме арқылы ұзартыңыз: egov-kz.online/ecp",
     "based_on": "https://bes.media/news/prodlite-etsp-novaya-shema-moshennichestva-poyavilas-v-kazahstane/"},
    {"id": "bank_security", "sender": "+7 707 112 45 90", "time": "11:05",
     "label": {"ru": "«Служба безопасности банка»", "kk": "«Банк қауіпсіздік қызметі»"},
     "text": "Служба безопасности банка: по вашей карте зафиксирована подозрительная операция на 480 000 тг. "
             "Если это не вы, срочно перезвоните по номеру +7 727 356 18 40",
     "based_on": "https://kz.kursiv.media/2025-12-31/svvo-tainyi-santa-i-zvonki-kak-moshenniki-obmanyvali-kazahstanczev-v-2025-godu/"},
    {"id": "olx", "sender": "Покупатель OLX", "time": "14:18", "label": {"ru": "«Оплата через OLX Доставку»", "kk": "«OLX жеткізу арқылы төлем»"},
     "text": "Здравствуйте! Я оплатил ваш товар через OLX Доставку. Чтобы получить деньги, перейдите по ссылке "
             "olx-kz.delivery-pay.site и введите данные карты",
     "based_on": "https://kz.kursiv.media/2025-12-31/svvo-tainyi-santa-i-zvonki-kak-moshenniki-obmanyvali-kazahstanczev-v-2025-godu/"},
    {"id": "relative", "sender": "+7 776 403 21 88", "time": "21:37", "label": {"ru": "«Мама, это мой новый номер»", "kk": "«Мама, бұл жаңа нөмірім»"},
     "text": "Мама, это мой новый номер. Попал в неприятность, срочно скинь 150 000 на карту 4400 4302 1188 4417, потом всё объясню",
     "based_on": "https://finance.kz/articles/kak-zashchititsya-ot-moshennikov-kazakhstan"},
    {"id": "drop", "sender": "Telegram", "time": "16:03", "label": {"ru": "«Подработка с картой»", "kk": "«Картамен қосымша жұмыс»"},
     "text": "Подработка для студентов! Оформи карту и передай её нам — 30 000 тг за неделю, без вложений. Пиши @easy_money_kz",
     "based_on": "https://bes.media/news/prodal-schet-sel-v-tyurmu-skolko-dropperov-osudili-v-2026/"},
    {"id": "legit_otp", "sender": "BCC", "time": "09:12", "label": {"ru": "Код подтверждения банка", "kk": "Банктің растау коды"},
     "text": "Код подтверждения: 4721. Никому не сообщайте этот код, даже сотрудникам банка.", "based_on": None},
    {"id": "legit_purchase", "sender": "BCC", "time": "18:40", "label": {"ru": "Уведомление о покупке", "kk": "Сатып алу туралы хабарлама"},
     "text": "Покупка 12 450 KZT. MAGNUM CASH&CARRY, Алматы. Доступно: 1 337 550 KZT", "based_on": None},
]


def render(s: dict) -> Image.Image:
    W, H = 720, 900
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)
    f_small = ImageFont.truetype(FONT, 26)
    f_head = ImageFont.truetype(BOLD, 34)
    f_text = ImageFont.truetype(FONT, 31)
    d.text((40, 22), s["time"], font=f_small, fill="#111")
    d.text((W - 150, 22), "LTE  87%", font=f_small, fill="#111")
    d.rectangle([0, 70, W, 200], fill="#f6f6f8")
    d.ellipse([W // 2 - 36, 82, W // 2 + 36, 154], fill="#b8bcc6")
    initial = s["sender"].lstrip("+")[0].upper()
    d.text((W // 2, 118), initial, font=f_head, fill="white", anchor="mm")
    d.text((W // 2, 178), s["sender"], font=f_small, fill="#111", anchor="mm")
    lines = []
    for para in s["text"].split("\n"):
        lines += textwrap.wrap(para, width=30) or [""]
    line_h = 42
    bubble_h = len(lines) * line_h + 40
    x0, y0 = 36, 250
    d.rounded_rectangle([x0, y0, x0 + 560, y0 + bubble_h], radius=34, fill="#e9e9eb")
    for i, ln in enumerate(lines):
        d.text((x0 + 26, y0 + 20 + i * line_h), ln, font=f_text, fill="#111")
    d.text((x0 + 8, y0 + bubble_h + 14), f"Сегодня {s['time']}", font=f_small, fill="#8a8a8e")
    d.rounded_rectangle([30, H - 100, W - 30, H - 40], radius=30, outline="#d1d1d6", width=2)
    d.text((60, H - 70), "Сообщение", font=f_small, fill="#b0b0b5", anchor="lm")
    return img


def main() -> None:
    OUT_IMG.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    meta = []
    for s in SAMPLES:
        render(s).save(OUT_IMG / f"{s['id']}.png", optimize=True)
        meta.append({"id": s["id"], "sender": s["sender"], "text": s["text"], "label": s["label"],
                     "image": f"/samples/{s['id']}.png", "based_on": s["based_on"], "constructed": True})
    OUT_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"{len(meta)} samples -> {OUT_IMG}")


if __name__ == "__main__":
    main()
