"""Rule-based fraud signals. Each rule explains its evidence so adjusters can verify it."""

import re
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Claim, Document
from app.schemas.claim import ClaimFacts, FraudFlag, Severity

_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")


@dataclass(frozen=True)
class FraudContext:
    claim_id: uuid.UUID
    facts: ClaimFacts
    submitted_on: date
    document_hashes: list[str]
    document_texts: list[str]
    ocr_confidences: list[float]
    llm_inconsistencies: list[str]


class FraudRuleEngine:
    def __init__(self, session: Session, policy_limit: Decimal | None = None) -> None:
        self.session = session
        self.policy_limit = policy_limit or Decimal(str(settings.policy_limit_default))

    def evaluate(self, ctx: FraudContext) -> list[FraudFlag]:
        flags: list[FraudFlag] = []
        flags += self._duplicate_documents(ctx)
        flags += self._date_checks(ctx)
        flags += self._amount_checks(ctx)
        flags += self._ocr_quality(ctx)
        flags += [
            FraudFlag(code="DOCUMENT_INCONSISTENCY", severity=Severity.MEDIUM, evidence=text)
            for text in ctx.llm_inconsistencies
        ]
        return flags

    def _duplicate_documents(self, ctx: FraudContext) -> list[FraudFlag]:
        if not ctx.document_hashes:
            return []
        rows = self.session.execute(
            select(Document.content_sha256, Claim.id, Claim.policy_number)
            .join(Claim, Claim.id == Document.claim_id)
            .where(Document.content_sha256.in_(ctx.document_hashes), Claim.id != ctx.claim_id)
        ).all()
        return [
            FraudFlag(
                code="DUPLICATE_DOCUMENT",
                severity=Severity.HIGH,
                evidence=f"An identical document was submitted with claim {row.id} (policy {row.policy_number}).",
            )
            for row in rows
        ]

    def _date_checks(self, ctx: FraudContext) -> list[FraudFlag]:
        loss = ctx.facts.loss_date
        if loss is None:
            return []
        flags = []
        if loss > ctx.submitted_on:
            flags.append(
                FraudFlag(
                    code="LOSS_AFTER_SUBMISSION",
                    severity=Severity.HIGH,
                    evidence=f"Loss date {loss} is after the claim was submitted on {ctx.submitted_on}.",
                )
            )
        earlier = sorted(
            {
                date(int(y), int(m), int(d))
                for text in ctx.document_texts
                for y, m, d in _DATE.findall(text)
                if 1 <= int(m) <= 12 and 1 <= int(d) <= 31 and _valid(int(y), int(m), int(d))
            }
        )
        invoices_before_loss = [d for d in earlier if (loss - d).days > 30]
        if invoices_before_loss:
            flags.append(
                FraudFlag(
                    code="DOCUMENT_PREDATES_LOSS",
                    severity=Severity.MEDIUM,
                    evidence=f"Documents are dated {invoices_before_loss[0]}, more than 30 days before the loss on {loss}.",
                )
            )
        return flags

    def _amount_checks(self, ctx: FraudContext) -> list[FraudFlag]:
        amount = ctx.facts.claimed_amount
        if amount is None:
            return []
        flags = []
        if amount > self.policy_limit:
            flags.append(
                FraudFlag(
                    code="AMOUNT_OVER_LIMIT",
                    severity=Severity.MEDIUM,
                    evidence=f"Claimed {amount} exceeds the policy limit of {self.policy_limit}.",
                )
            )
        if amount >= 1000 and amount % 1000 == 0:
            flags.append(
                FraudFlag(
                    code="ROUND_AMOUNT",
                    severity=Severity.LOW,
                    evidence=f"Claimed amount {amount} is a round number, which is unusual for itemised repairs.",
                )
            )
        return flags

    def _ocr_quality(self, ctx: FraudContext) -> list[FraudFlag]:
        low = [c for c in ctx.ocr_confidences if c < settings.low_ocr_confidence]
        if not low:
            return []
        return [
            FraudFlag(
                code="LOW_OCR_CONFIDENCE",
                severity=Severity.LOW,
                evidence=f"{len(low)} document(s) were hard to read (confidence {min(low):.0%}); facts may be wrong.",
            )
        ]


def _valid(y: int, m: int, d: int) -> bool:
    try:
        date(y, m, d)
        return True
    except ValueError:
        return False
