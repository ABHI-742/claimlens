"""SQLAlchemy models (docs/diagrams/er-diagram.md)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id"))
    team: Mapped[Team] = relationship()


class RefreshToken(Base):
    """Single-use refresh token. Only the SHA-256 hash of the token is stored."""

    __tablename__ = "refresh_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    policy_number: Mapped[str] = mapped_column(String(32), index=True)
    product: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    queue: Mapped[str | None] = mapped_column(String(20), index=True)
    triage_score: Mapped[float | None] = mapped_column(Float)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id"))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)

    documents: Mapped[list["Document"]] = relationship(back_populates="claim", order_by="Document.filename")
    facts: Mapped["ClaimFactsRow | None"] = relationship(uselist=False, cascade="all, delete-orphan")
    coverage: Mapped["CoverageAssessmentRow | None"] = relationship(
        uselist=False, cascade="all, delete-orphan"
    )
    fraud_flags: Mapped[list["FraudFlagRow"]] = relationship(cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    s3_key: Mapped[str] = mapped_column(String(500))
    content_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    ocr_text_masked: Mapped[str | None] = mapped_column(Text)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    claim: Mapped[Claim] = relationship(back_populates="documents")


class ClaimFactsRow(Base):
    __tablename__ = "claim_facts"
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True)
    loss_date: Mapped[date | None] = mapped_column(Date)
    loss_type: Mapped[str] = mapped_column(String(80))
    location: Mapped[str | None] = mapped_column(String(255))
    claimed_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[float] = mapped_column(Float)
    inconsistencies: Mapped[list] = mapped_column(JSON, default=list)


class CoverageAssessmentRow(Base):
    __tablename__ = "coverage_assessments"
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True)
    verdict: Mapped[str] = mapped_column(String(20))
    reasoning: Mapped[str] = mapped_column(Text)
    uncertainty: Mapped[float] = mapped_column(Float)
    cited_clause_ids: Mapped[list] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(String(60))


class FraudFlagRow(Base):
    __tablename__ = "fraud_flags"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(10))
    evidence: Mapped[str] = mapped_column(Text)


class PolicyDocument(Base):
    __tablename__ = "policy_documents"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    product: Mapped[str] = mapped_column(String(40), index=True)
    version: Mapped[str] = mapped_column(String(20))
    s3_key: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="UPLOADING")
    chunks: Mapped[list["PolicyChunk"]] = relationship(cascade="all, delete-orphan")


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    policy_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policy_documents.id", ondelete="CASCADE"), index=True
    )
    product: Mapped[str] = mapped_column(String(40), index=True)
    clause_id: Mapped[str] = mapped_column(String(60))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dimensions))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), index=True
    )
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(60))
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
