"""In-memory demo state. Deterministic seed, reset via POST /api/demo/reset.

Everything a real bank already has (accounts, outbound call log, complaint registry, the
Antifraud-Centre list) is mocked here with the same shape the production integration would use.
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
    guardian_id: str | None = None
    family_limit: float = 200_000
    known_accounts: set[str] = field(default_factory=set)
    avatar: str = ""


@dataclass
class Account:
    number: str  # digits only
    display: str
    holder: str
    bank: str
    complaints: int = 0
    in_afc: bool = False


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


@dataclass
class FamilyRequest:
    id: str
    transfer_id: str
    from_client: str
    guardian_id: str
    created: float
    expires: float
    status: Literal["pending", "approved", "declined", "expired"] = "pending"


@dataclass
class Event:
    seq: int
    ts: float
    kind: str
    client_id: str | None
    text: str
    step: StepId | None = None
    stopped: bool = False


FAMILY_TIMEOUT_S = 15 * 60
SCAM_NUMBER = "+7 727 356 18 40"
BANK_NUMBER = "505"


class State:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.reset()

    # ------------------------------------------------------------------ seed
    def reset(self) -> None:
        with self.lock:
            self._ids = itertools.count(1)
            self.clients: dict[str, Client] = {
                "aigerim": Client("aigerim", "Айгерим Сейткали", "Айгерим", 52, "Алматы", "kk", 1_350_000,
                                  guardian_id="erzhan", known_accounts={digits("KZ55 8562 0000 0128 7740")}, avatar="АС"),
                "erzhan": Client("erzhan", "Ержан Сейткали", "Ержан", 27, "Астана", "ru", 420_000, avatar="ЕС",
                                 known_accounts={digits("KZ55 8562 0000 0128 7740")}),
                "madina": Client("madina", "Мадина Каримова", "Мадина", 34, "Алматы", "ru", 610_000, avatar="МК",
                                 known_accounts={digits("KZ21 8562 0000 0390 5512")}),
            }
            accs = [
                Account(digits("KZ86 8562 0000 0471 1934"), "KZ86 8562 0000 0471 1934", "Данияр Б.", "BCC"),
                Account(digits("KZ55 8562 0000 0128 7740"), "KZ55 8562 0000 0128 7740", "Сауле С.", "BCC"),
                Account(digits("KZ21 8562 0000 0390 5512"), "KZ21 8562 0000 0390 5512", "Асхат Т.", "BCC"),
                Account(digits("4400 4302 1188 4417"), "4400 •••• •••• 4417", "Нурлан К.", "Другой банк", in_afc=True),
            ]
            self.accounts: dict[str, Account] = {a.number: a for a in accs}
            self.number_complaints: dict[str, int] = {SCAM_NUMBER: 3}
            self.calls: dict[str, Call] = {}
            self.last_call_number: dict[str, str] = {}
            self.bank_outbound: dict[str, Call] = {}  # bank's own call log: client_id -> active outbound call
            self.sms: dict[str, list[Sms]] = {cid: [] for cid in self.clients}
            self.prefill: dict[str, dict | None] = {cid: None for cid in self.clients}
            self.nav: dict[str, dict | None] = {cid: None for cid in self.clients}
            self.transfers: dict[str, Transfer] = {}
            self.family: dict[str, FamilyRequest] = {}
            self.events: list[Event] = []
            self.steps: set[str] = set()
            self.stopped = 0
            self._seq = itertools.count(1)
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

    def account(self, raw: str) -> Account:
        num = digits(raw)
        acc = self.accounts.get(num)
        if acc is None:  # unknown account typed by hand: treat as a new external recipient
            acc = Account(num, raw.strip(), "Получатель", "Другой банк")
            self.accounts[num] = acc
        return acc

    def end_call(self, cid: str) -> None:
        with self.lock:
            call = self.calls.pop(cid, None)
            if call:
                self.last_call_number[cid] = call.number
                self.bank_outbound.pop(cid, None)

    def expire_family(self) -> None:
        now = time.time()
        for fr in self.family.values():
            if fr.status == "pending" and now > fr.expires:
                fr.status = "expired"
                tr = self.transfers[fr.transfer_id]
                tr.status = "escalated"
                self.emit("family_expired", fr.from_client, "Доверенное лицо не ответило — перевод передан сотруднику банка")


STATE = State()
