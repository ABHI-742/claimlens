"""Route a processed claim to a review queue (docs/architecture.md, section 5)."""

from dataclasses import dataclass
from decimal import Decimal

from app.core.config import Settings, settings
from app.schemas.claim import CoverageAssessment, CoverageVerdict, FraudFlag, Severity, TriageQueue

_FRAUD_WEIGHT = {Severity.LOW: 0.2, Severity.MEDIUM: 0.5, Severity.HIGH: 1.0}


@dataclass(frozen=True)
class TriageResult:
    score: float
    queue: TriageQueue


class TriageScorer:
    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    def score(
        self,
        severity: float,
        claimed_amount: Decimal | None,
        coverage: CoverageAssessment,
        flags: list[FraudFlag],
    ) -> TriageResult:
        fraud_risk = max((_FRAUD_WEIGHT[f.severity] for f in flags), default=0.0)
        c = self.config
        score = round(
            c.triage_weight_severity * severity
            + c.triage_weight_fraud * fraud_risk
            + c.triage_weight_uncertainty * coverage.uncertainty,
            4,
        )

        if any(f.severity == Severity.HIGH for f in flags) or score > c.triage_investigate_min_score:
            queue = TriageQueue.INVESTIGATE
        elif (
            score < c.triage_fast_track_max_score
            and not flags
            and coverage.verdict == CoverageVerdict.COVERED
            and claimed_amount is not None
            and claimed_amount < Decimal(str(c.triage_fast_track_max_amount))
        ):
            queue = TriageQueue.FAST_TRACK
        else:
            queue = TriageQueue.STANDARD

        return TriageResult(score=score, queue=queue)
