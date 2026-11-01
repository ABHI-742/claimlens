from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


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


class DocumentIn(BaseModel):
    filename: str
    mime_type: str


class ClaimCreate(BaseModel):
    policy_number: str = Field(min_length=4, max_length=32)
    product: str
    documents: list[DocumentIn] = Field(min_length=1, max_length=20)


class UploadTarget(BaseModel):
    document_id: UUID
    upload_url: str


class ClaimCreated(BaseModel):
    claim_id: UUID
    uploads: list[UploadTarget]


class ClaimFacts(BaseModel):
    """Structured output the extractor asks Claude to fill in."""

    loss_date: date | None
    loss_type: str
    location: str | None
    claimed_amount: Decimal | None
    description: str


class CoverageAssessment(BaseModel):
    verdict: CoverageVerdict
    reasoning: str
    cited_clause_ids: list[str] = Field(min_length=1)
    uncertainty: float = Field(ge=0, le=1)


class FraudFlag(BaseModel):
    code: str
    severity: Severity
    evidence: str


class ClaimDetail(BaseModel):
    id: UUID
    policy_number: str
    status: ClaimStatus
    queue: TriageQueue | None
    triage_score: float | None
    submitted_at: datetime | None
    facts: ClaimFacts | None
    coverage: CoverageAssessment | None
    fraud_flags: list[FraudFlag]


class ClaimDecision(BaseModel):
    decision: DecisionType
    note: str = Field(max_length=2000)
