from decimal import Decimal

from app.schemas.claim import CoverageAssessment, CoverageVerdict, FraudFlag, Severity, TriageQueue
from app.services.triage import TriageScorer


def coverage(uncertainty: float) -> CoverageAssessment:
    return CoverageAssessment(
        verdict=CoverageVerdict.COVERED,
        reasoning="Water damage from a burst pipe is covered.",
        cited_clause_ids=["HO3-SEC1-A"],
        uncertainty=uncertainty,
    )


def test_small_clean_claim_is_fast_tracked():
    result = TriageScorer().score(0.2, Decimal("1200"), coverage(0.1), [])
    assert result.queue == TriageQueue.FAST_TRACK


def test_high_severity_fraud_flag_forces_investigation():
    flag = FraudFlag(code="DUPLICATE_INVOICE", severity=Severity.HIGH, evidence="Same invoice on claim 81")
    result = TriageScorer().score(0.1, Decimal("900"), coverage(0.1), [flag])
    assert result.queue == TriageQueue.INVESTIGATE


def test_large_claim_goes_to_standard_review():
    result = TriageScorer().score(0.2, Decimal("40000"), coverage(0.1), [])
    assert result.queue == TriageQueue.STANDARD


def test_high_score_goes_to_investigation():
    flag = FraudFlag(code="DATE_MISMATCH", severity=Severity.MEDIUM, evidence="Invoice predates loss date")
    result = TriageScorer().score(1.0, Decimal("40000"), coverage(1.0), [flag])
    assert result.score > 0.65
    assert result.queue == TriageQueue.INVESTIGATE
