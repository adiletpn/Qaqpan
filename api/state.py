"""In-memory demo state. Deterministic seed, reset via the director.

Everything a real bank already has (accounts, outbound call log, complaint registry, the
Antifraud-Centre list, family links) is mocked here with the shape a production integration would use.
The bank does NOT see the client's SMS or call audio: the timeline only holds what Qaqpan itself knows
(messages the client checked, the fact of a call from the OS, call checks, transfers).
"""

from __future__ import annotations

import itertools
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Literal

Lang = Literal["ru", "kk"]
TransferStatus = Literal["completed", "warning", "questions", "held", "awaiting_family", "cancelled", "escalated"]
StepId = Literal["written", "called", "persuaded", "received"]

FAMILY_TIMEOUT_S = 15 * 60
PRESSURE_WINDOW_S = 30 * 60   # «положите трубку и переведите сами» — the call still counts for 30 minutes
SESSION_WINDOW_S = 24 * 3600  # recipients first paid within 24 h stay «new»; the shield limit counts 24 h of transfers
SHIELD_DISABLE_DELAY_S = 24 * 3600
SCAM_NUMBER = "+7 727 356 18 40"
BANK_NUMBER = "505"
NATIVE_NUMBER = "native"


def digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


@dataclass
class Client:
    id: str
    name: str
    short: str
    age: int
    city: str
    lang: Lang
    balance: float
    phone: str
    avatar: str = ""
    known_accounts: set[str] = field(default_factory=set)  # long-standing recipients (older than the session)
    loan: tuple[float, float] | None = None  # (amount, issued_ts) of the latest loan


@dataclass
class FamilyLink:
    """Voluntary link: the ward invites a guardian, the guardian accepts. Disabling takes 24 h."""

    ward_id: str
    guardian_id: str
    ward_title: dict[str, str]      # how the guardian calls the ward: «Мама» / «Анаңыз»
    ward_title_dat: dict[str, str]  # «маме» / «анаңызға»
    ward_title_acc: dict[str, str]  # «Маму» / «Анаңызды»
    guardian_title: dict[str, str]  # how the ward calls the guardian: «сын» / «ұлыңыз»
    limit: float = 200_000
    disable_at: float | None = None

    def active(self, now: float | None = None) -> bool:
        return self.disable_at is None or (now or time.time()) < self.disable_at


@dataclass
class Account:
    number: str  # digits only
    display: str
    holder: str
    bank: str
    complaints: int = 0  # confirmed: about a transfer Qaqpan itself stopped under pressure
    signals: int = 0     # unconfirmed: complaint by number only, a guardian's «no» — adds weight, never a hold alone
    in_afc: bool = False
    owner_id: str | None = None  # set when the account belongs to one of our clients (e.g. own card elsewhere)


@dataclass
class Call:
    number: str
    caller_label: str
    started: float
    answered: bool = False
    is_bank: bool = False
    employee: str | None = None
    department: str | None = None


@dataclass
class Sms:
    id: str
    sender: str
    text: str
    sample_id: str | None
    ts: float


@dataclass
class Transfer:
    id: str
    client_id: str
    account: str
    amount: float
    ts: float
    score: float
    level: int
    reasons: list[str]
    reason_kw: dict
    template: str
    status: TransferStatus
    answers: list[bool] | None = None
    family_request_id: str | None = None
    note: str = ""
    shield: bool = False    # the family shield applies (new recipient, session total >= the guardian limit)
    pressure: bool = False  # made during a call or within 30 min after it


@dataclass
class FamilyRequest:
    id: str
    transfer_id: str
    from_client: str
    guardian_id: str
    created: float
    expires: float
    status: Literal["pending", "approved", "declined", "expired", "withdrawn"] = "pending"


@dataclass
class Alert:
    """What Qaqpan knows about a client today — shown to the guardian as a timeline."""

    ts: float
    text: dict[str, str]


@dataclass
class Notice:
    """Push notification to a phone (lock-screen banner)."""

    id: str
    ts: float
    kind: Literal["family_request", "shield_disable", "info"]
    title: dict[str, str]
    body: dict[str, str]
    ref: str | None = None
    seen: bool = False


@dataclass
class Event:
    seq: int
    ts: float
    kind: str
    client_id: str | None
    text: str
    step: StepId | None = None
    stopped: bool = False


class State:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.reset()

    # ------------------------------------------------------------------ seed
    def reset(self) -> None:
        with self.lock:
            self.epoch = getattr(self, "epoch", 0) + 1  # phones return to the home screen when it changes
            self._ids = itertools.count(1)
            self._seq = itertools.count(1)
            sister = digits("KZ55 8562 0000 0128 7740")
            own_card = digits("5169 4971 0023 7781")
            self.clients: dict[str, Client] = {
                "aigerim": Client("aigerim", "Айгерим Сейткали", "Айгерим", 52, "Алматы", "kk", 1_350_000,
                                  "+7 701 555 12 45", "АС", {sister, own_card}),
                "erzhan": Client("erzhan", "Ержан Сейткали", "Ержан", 27, "Астана", "ru", 420_000,
                                 "+7 702 555 33 18", "ЕС", {sister}),
                "madina": Client("madina", "Мадина Каримова", "Мадина", 34, "Алматы", "ru", 610_000,
                                 "+7 705 555 76 02", "МК", {digits("KZ21 8562 0000 0390 5512")}),
            }
            # ordinary account history so the app looks lived-in (static demo data)
            def h(ru, kk, amount, ago_min):
                return {"title": {"ru": ru, "kk": kk}, "amount": amount, "ago_min": ago_min}
            self.history: dict[str, list[dict]] = {
                "aigerim": [h("Magnum Cash&Carry", "Magnum Cash&Carry", -12_450, 190), h("Перевод от дочери", "Қызынан аударым", 50_000, 1500),
                            h("Казахтелеком · интернет", "Қазақтелеком · интернет", -7_990, 2900), h("Аптека «Biosfera»", "«Biosfera» дәріханасы", -4_320, 4300)],
                "erzhan": [h("Зарплата", "Жалақы", 512_000, 1450), h("Yandex Go", "Yandex Go", -2_350, 95), h("Small · продукты", "Small · азық-түлік", -8_740, 300),
                           h("Kcell · связь", "Kcell · байланыс", -4_500, 2800)],
                "madina": [h("Зарплата", "Жалақы", 390_000, 2600), h("Wildberries", "Wildberries", -18_900, 220), h("Starbucks", "Starbucks", -2_100, 40),
                           h("Сергек · штраф оплачен", "Сергек · айыппұл төленді", -14_768, 3900)],
            }
            self.links: dict[str, FamilyLink] = {
                "aigerim": FamilyLink("aigerim", "erzhan", {"ru": "Мама", "kk": "Анаңыз"},
                                      {"ru": "маме", "kk": "анаңызға"}, {"ru": "Маму", "kk": "Анаңызды"},
                                      {"ru": "сын", "kk": "ұлыңыз"}),
            }
            accs = [
                Account(digits("KZ86 8562 0000 0471 1934"), "KZ86 8562 0000 0471 1934", "Данияр Б.", "BCC"),
                Account(sister, "KZ55 8562 0000 0128 7740", "Сауле С.", "BCC"),
                Account(digits("KZ21 8562 0000 0390 5512"), "KZ21 8562 0000 0390 5512", "Асхат Т.", "BCC"),
                Account(digits("4400 4302 1188 4417"), "4400 •••• •••• 4417", "Нурлан К.", "Другой банк", in_afc=True),
                Account(own_card, "5169 •••• •••• 7781", "Айгерим С. (своя карта)", "Другой банк", owner_id="aigerim"),
            ]
            self.accounts: dict[str, Account] = {a.number: a for a in accs}
            self.complaints_by: set[tuple[str, str]] = set()  # (client_id, account) — one complaint or «no» each
            self.confirmed_by: set[tuple[str, str]] = set()   # of those, confirmed by a stopped transfer
            self.number_complaints: dict[str, int] = {SCAM_NUMBER: 3}
            self.calls: dict[str, Call] = {}
            self.call_ended: dict[str, float] = {}  # when the client's last non-bank call ended
            self.first_paid: dict[tuple[str, str], float] = {}  # (client, account) -> first completed transfer
            self.saved_ids: set[str] = set()
            self.saved = 0.0  # ₸ in transfers Qaqpan stopped
            self.last_call_number: dict[str, str] = {}
            self.bank_outbound: dict[str, Call] = {}  # the bank's own call log: client_id -> active outbound call
            self.sms: dict[str, list[Sms]] = {cid: [] for cid in self.clients}
            self.prefill: dict[str, dict | None] = {cid: None for cid in self.clients}
            self.nav: dict[str, dict | None] = {cid: None for cid in self.clients}
            self.alerts: dict[str, list[Alert]] = {cid: [] for cid in self.clients}
            self.notices: dict[str, list[Notice]] = {cid: [] for cid in self.clients}
            self.transfers: dict[str, Transfer] = {}
            self.family: dict[str, FamilyRequest] = {}
            self.events: list[Event] = []
            self.steps: set[str] = set()
            self.stopped = 0
            self.emit("reset", None, "Демо сброшено")

    # ------------------------------------------------------------------ helpers
    def new_id(self, prefix: str) -> str:
        return f"{prefix}{next(self._ids):04d}"

    def emit(self, kind: str, client_id: str | None, text: str, step: StepId | None = None, stopped: bool = False) -> None:
        with self.lock:
            self.events.append(Event(next(self._seq), time.time(), kind, client_id, text, step, stopped))
            if step:
                self.steps.add(step)
            if stopped:
                self.stopped += 1
            self.events = self.events[-200:]

    def alert(self, cid: str | None, ru: str, kk: str) -> None:
        if cid in self.alerts:
            self.alerts[cid].append(Alert(time.time(), {"ru": ru, "kk": kk}))
            self.alerts[cid] = self.alerts[cid][-20:]

    def notify(self, cid: str, kind: str, title: dict[str, str], body: dict[str, str], ref: str | None = None) -> None:
        self.notices[cid].append(Notice(self.new_id("N"), time.time(), kind, title, body, ref))  # type: ignore[arg-type]

    def link_for_ward(self, cid: str) -> FamilyLink | None:
        link = self.links.get(cid)
        return link if link and link.active() else None

    def links_for_guardian(self, cid: str) -> list[FamilyLink]:
        return [lk for lk in self.links.values() if lk.guardian_id == cid]

    def account(self, raw: str) -> Account:
        num = digits(raw)
        acc = self.accounts.get(num)
        if acc is None:  # unknown account typed by hand: a new external recipient
            acc = Account(num, raw.strip(), "Получатель", "Другой банк")
            self.accounts[num] = acc
        return acc

    def end_call(self, cid: str) -> None:
        with self.lock:
            call = self.calls.pop(cid, None)
            if call:
                if call.number != NATIVE_NUMBER:
                    self.last_call_number[cid] = call.number
                if call.answered and not call.is_bank and cid not in self.bank_outbound:
                    self.call_ended[cid] = time.time()
                self.bank_outbound.pop(cid, None)

    def pressure(self, cid: str) -> tuple[bool, bool]:
        """(on a call now, a call ended less than 30 minutes ago). A verified bank call is not pressure."""
        call = self.calls.get(cid)
        on_call = bool(call and call.answered and cid not in self.bank_outbound)
        ended = self.call_ended.get(cid)
        return on_call, (not on_call and ended is not None and time.time() - ended < PRESSURE_WINDOW_S)

    def is_known(self, cid: str, account: str, now: float | None = None) -> bool:
        """A recipient becomes «known» only a day after the first payment: a test transfer of 100 ₸ whitelists nothing."""
        if account in self.clients[cid].known_accounts:
            return True
        first = self.first_paid.get((cid, account))
        return first is not None and (now or time.time()) - first >= SESSION_WINDOW_S

    def session_total(self, cid: str, now: float | None = None) -> float:
        """Money sent or being sent to new recipients in the last 24 h — splitting 900 000 into five parts adds up."""
        now = now or time.time()
        return sum(tr.amount for tr in self.transfers.values()
                   if tr.client_id == cid and tr.status != "cancelled" and now - tr.ts < SESSION_WINDOW_S
                   and not self.is_known(cid, tr.account, now))

    def mark_saved(self, tr: "Transfer") -> None:
        if tr.id not in self.saved_ids:
            self.saved_ids.add(tr.id)
            self.saved += tr.amount

    def expire_family(self) -> None:
        now = time.time()
        for fr in self.family.values():
            if fr.status == "pending" and now > fr.expires:
                fr.status = "expired"
                tr = self.transfers[fr.transfer_id]
                tr.status = "escalated"
                self.emit("family_expired", fr.from_client, "Доверенное лицо не ответило — перевод ждёт проверки антифрод-аналитика банка")


STATE = State()
