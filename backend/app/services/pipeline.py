"""Claim processing pipeline (docs/architecture.md, section 4)."""

import hashlib
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Claim, ClaimFactsRow, CoverageAssessmentRow, FraudFlagRow
from app.schemas.claim import ClaimStatus
from app.services import audit
from app.services.coverage import CitationError
from app.services.fraud import FraudContext, FraudRuleEngine
from app.services.interfaces import ClaimExtractor, CoverageAssessor, OcrProvider, PolicyRetriever
from app.services.pii import PiiMasker
from app.services.storage import Storage
from app.services.triage import TriageScorer

log = logging.getLogger("claimlens.pipeline")
ACTOR = "system:pipeline"


class ClaimPipeline:
    def __init__(
        self,
        session: Session,
        storage: Storage,
        ocr: OcrProvider,
        extractor: ClaimExtractor,
        retriever: PolicyRetriever,
        assessor: CoverageAssessor,
        fraud: FraudRuleEngine | None = None,
        masker: PiiMasker | None = None,
        scorer: TriageScorer | None = None,
        model_name: str = settings.anthropic_model,
        today: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.session = session
        self.storage = storage
        self.ocr = ocr
        self.extractor = extractor
        self.retriever = retriever
        self.assessor = assessor
        self.fraud = fraud or FraudRuleEngine(session)
        self.masker = masker or PiiMasker()
        self.scorer = scorer or TriageScorer()
        self.model_name = model_name
        self.today = today

    def run(self, claim_id: uuid.UUID) -> Claim:
        claim = self.session.get(Claim, claim_id)
        if claim is None:
            raise LookupError(f"Claim {claim_id} not found")
        if claim.status not in (ClaimStatus.SUBMITTED, ClaimStatus.PROCESSING):
            log.info("Skipping claim %s in status %s (already processed)", claim_id, claim.status)
            return claim

        claim.status = ClaimStatus.PROCESSING
        audit.record(self.session, claim.id, ACTOR, "processing.started")
        self.session.commit()

        # 1. OCR and PII masking, per document (idempotent: masked text is overwritten)
        masked_texts, hashes, confidences = [], [], []
        for doc in claim.documents:
            data = self.storage.get_bytes(doc.s3_key)
            doc.content_sha256 = hashlib.sha256(data).hexdigest()
            result = self.ocr.extract(data, doc.mime_type)
            masked = self.masker.mask(result.text)
            doc.ocr_text_masked = masked.text
            doc.ocr_confidence = result.confidence
            masked_texts.append(f'<document name="{doc.filename}">\n{masked.text}\n</document>')
            hashes.append(doc.content_sha256)
            confidences.append(result.confidence)
        self.session.flush()

        # 2. Structured extraction
        extraction = self.extractor.extract("\n\n".join(masked_texts), claim.product)
        facts = extraction.facts

        # 3. Retrieval-augmented coverage assessment (one retry if citations are invalid)
        query = f"{facts.loss_type}. {facts.description}"
        clauses = self.retriever.top_k(query, claim.product, settings.retrieval_top_k)
        try:
            coverage = self.assessor.assess(facts, clauses)
        except CitationError:
            log.warning("Invalid citations for claim %s; retrying once", claim.id)
            coverage = self.assessor.assess(facts, clauses)

        # 4. Fraud signals and triage
        submitted_on = (claim.submitted_at or self.today()).date()
        flags = self.fraud.evaluate(
            FraudContext(
                claim_id=claim.id,
                facts=facts,
                submitted_on=submitted_on,
                document_hashes=hashes,
                document_texts=[d.ocr_text_masked or "" for d in claim.documents],
                ocr_confidences=confidences,
                llm_inconsistencies=extraction.inconsistencies,
            )
        )
        triage = self.scorer.score(extraction.severity, facts.claimed_amount, coverage, flags)

        # 5. Persist (replace any partial results from a previous attempt)
        for previous in (claim.facts, claim.coverage, *claim.fraud_flags):
            if previous is not None:
                self.session.delete(previous)
        self.session.flush()
        self.session.expire(claim, ["facts", "coverage", "fraud_flags"])
        claim.facts = ClaimFactsRow(
            loss_date=facts.loss_date,
            loss_type=facts.loss_type,
            location=facts.location,
            claimed_amount=facts.claimed_amount,
            description=facts.description,
            severity=extraction.severity,
            inconsistencies=extraction.inconsistencies,
        )
        claim.coverage = CoverageAssessmentRow(
            verdict=coverage.verdict,
            reasoning=coverage.reasoning,
            uncertainty=coverage.uncertainty,
            cited_clause_ids=coverage.cited_clause_ids,
            model=self.model_name,
        )
        claim.fraud_flags = [
            FraudFlagRow(code=f.code, severity=f.severity, evidence=f.evidence) for f in flags
        ]
        claim.triage_score = triage.score
        claim.queue = triage.queue
        claim.status = ClaimStatus.READY_FOR_REVIEW
        claim.failure_reason = None
        audit.record(
            self.session,
            claim.id,
            ACTOR,
            "processing.completed",
            after={
                "queue": triage.queue,
                "score": triage.score,
                "verdict": coverage.verdict,
                "flags": [f.code for f in flags],
                "model": self.model_name,
            },
        )
        self.session.commit()
        return claim

    def mark_failed(self, claim_id: uuid.UUID, reason: str) -> None:
        self.session.rollback()
        claim = self.session.get(Claim, claim_id)
        if claim is None:
            return
        claim.status = ClaimStatus.FAILED
        claim.failure_reason = reason[:2000]
        audit.record(self.session, claim.id, ACTOR, "processing.failed", after={"reason": reason[:500]})
        self.session.commit()
