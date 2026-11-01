from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClaimStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PROCESSING = "PROCESSING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    AWAITING_INFO = "AWAITING_INFO"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    FAILED = "FAILED"
    CLOSED = "CLOSED"


class TriageQueue(StrEnum):
    FAST_TRACK = "FAST_TRACK"
    STANDARD = "STANDARD"
    INVESTIGATE = "INVESTIGATE"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CoverageVerdict(StrEnum):
    COVERED = "COVERED"
    NOT_COVERED = "NOT_COVERED"
    UNCLEAR = "UNCLEAR"


class DecisionType(StrEnum):
    APPROVE = "APPROVE"
    REQUEST_INFO = "REQUEST_INFO"
    ESCALATE = "ESCALATE"
    DENY = "DENY"


ALLOWED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/tiff", "text/plain"}


class DocumentIn(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    mime_type: str


class ClaimCreate(BaseModel):
    policy_number: str = Field(min_length=4, max_length=32)
    product: str = Field(min_length=2, max_length=40)
    documents: list[DocumentIn] = Field(min_length=1, max_length=20)


class UploadTarget(BaseModel):
    document_id: UUID
    filename: str
    upload_url: str


class ClaimCreated(BaseModel):
    claim_id: UUID
    uploads: list[UploadTarget]


class ClaimFacts(BaseModel):
    """Structured facts extracted from the claim documents."""

    model_config = ConfigDict(from_attributes=True)

    loss_date: date | None
    loss_type: str
    location: str | None
    claimed_amount: Decimal | None
    description: str


class CoverageAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    verdict: CoverageVerdict
    reasoning: str
    cited_clause_ids: list[str] = Field(min_length=1)
    uncertainty: float = Field(ge=0, le=1)


class FraudFlag(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    severity: Severity
    evidence: str


class Citation(BaseModel):
    clause_id: str
    content: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    mime_type: str
    ocr_confidence: float | None


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    actor: str
    action: str
    after: dict | None
    at: datetime


class ClaimSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    policy_number: str
    product: str
    status: ClaimStatus
    queue: TriageQueue | None
    triage_score: float | None
    submitted_at: datetime | None
    claimed_amount: Decimal | None = None
    flag_count: int = 0


class ClaimDetail(ClaimSummary):
    severity: float | None
    failure_reason: str | None
    facts: ClaimFacts | None
    inconsistencies: list[str]
    coverage: CoverageAssessment | None
    citations: list[Citation]
    fraud_flags: list[FraudFlag]
    documents: list[DocumentOut]
    audit: list[AuditEventOut]


class ClaimDecision(BaseModel):
    decision: DecisionType
    note: str = Field(min_length=1, max_length=2000)


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class PolicyCreate(BaseModel):
    product: str = Field(min_length=2, max_length=40)
    version: str = Field(min_length=1, max_length=20)
    mime_type: str = "application/pdf"


class PolicyCreated(BaseModel):
    policy_id: UUID
    upload_url: str


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product: str
    version: str
    status: str
