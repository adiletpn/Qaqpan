"""API contracts (request/response). OpenAPI -> web/src/api/types.ts via `make types`."""

from typing import Literal

from pydantic import BaseModel, Field

from .msgcheck import CheckResult
from .victim import VictimHelp

Lang = Literal["ru", "kk"]

__all__ = ["CheckResult", "VictimHelp"]


class MessageCheckRequest(BaseModel):
    client_id: str | None = None
    text: str | None = Field(default=None, max_length=5000)
    image_b64: str | None = Field(default=None, max_length=8_000_000)
    media_type: Literal["image/png", "image/jpeg", "image/webp", "image/gif"] = "image/png"
    sample_id: str | None = None
    lang: Lang = "ru"


class CallVerifyRequest(BaseModel):
    client_id: str
    lang: Lang | None = None


class CallVerifyResult(BaseModel):
    status: Literal["bank", "not_bank", "no_call"]
    title: str
    message: str
    number: str | None = None
    number_complaints: int = 0


class TransferContext(BaseModel):
    pasted: bool = False
    app_switches: int = 0


class TransferRequest(BaseModel):
    client_id: str
    account: str = Field(min_length=6, max_length=40)
    amount: float = Field(gt=0, le=100_000_000)
    context: TransferContext = TransferContext()


class Question(BaseModel):
    id: int
    text: str


class TransferView(BaseModel):
    id: str
    status: str
    level: int
    score: float
    amount: float
    account: str
    holder: str
    title: str | None = None
    message: str | None = None
    questions: list[Question] = []
    reasons: list[str] = []
    guardian_name: str | None = None
    balance: float
    release_at: float | None = None   # «Отложить на час»: when it goes out by itself
    analysis: dict | None = None      # Qaqpan's conclusion during the hour (approved texts)


class AnswersRequest(BaseModel):
    answers: list[bool] = Field(min_length=3, max_length=3)


class FamilyDecision(BaseModel):
    client_id: str  # who decides: must be the guardian of this request
    approve: bool


class RecipientCheck(BaseModel):
    client_id: str
    account: str = Field(min_length=6, max_length=40)


class CodewordRequest(BaseModel):
    agreed: bool


class ComplaintRequest(BaseModel):
    client_id: str
    transfer_id: str | None = None
    account: str | None = None


class ComplaintResult(BaseModel):
    message: str
    account_complaints: int
    confirmed: bool = False  # about a transfer Qaqpan stopped under pressure -> holds transfers of other clients
    number_flagged: str | None = None


class VictimRequest(BaseModel):
    client_id: str
    transfer_id: str | None = None
    story: str | None = Field(default=None, max_length=3000)
    lang: Lang | None = None


class NativeCallSignal(BaseModel):
    """Sent by the native wrapper (Android AudioManager.getMode / iOS CXCallObserver): only the fact of a call."""

    on_call: bool


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class AssistantRequest(BaseModel):
    client_id: str
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    lang: Lang | None = None
