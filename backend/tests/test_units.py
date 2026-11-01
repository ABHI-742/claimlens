"""Unit tests that need no database or network."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.security import hash_password, verify_password
from app.services.chunking import chunk_policy
from app.services.coverage import CitationError, ClaudeCoverageAssessor
from app.services.embeddings import HashEmbeddings
from app.services.extraction import ClaudeClaimExtractor
from app.services.interfaces import RetrievedClause
from app.services.llm import ClaudeStructuredLlm, LlmRefusalError
from evals.sample_policy import POLICY_TEXT
from tests.conftest import FakeLlm


def test_password_hashing_round_trip():
    stored = hash_password("s3cret")
    assert verify_password("s3cret", stored)
    assert not verify_password("wrong", stored)
    assert stored != hash_password("s3cret")  # salted


def test_chunking_splits_on_headings_with_stable_ids():
    chunks = chunk_policy(POLICY_TEXT, prefix="HO3-2026")
    ids = [c.clause_id for c in chunks]
    assert len(ids) == len(set(ids))
    water = next(c for c in chunks if "burst pipe" in c.content)
    assert water.clause_id == "HO3-2026-1-WATER-DAMAGE"
    assert chunk_policy(POLICY_TEXT, prefix="HO3-2026") == chunks


def test_chunking_windows_long_sections():
    text = "EXCLUSIONS\n" + " ".join(f"word{i}" for i in range(1000))
    chunks = chunk_policy(text, prefix="P", max_words=400, overlap_words=40)
    assert len(chunks) == 3
    assert chunks[1].clause_id == "P-EXCLUSIONS-2"


def test_hash_embeddings_rank_related_text_higher():
    emb = HashEmbeddings(dimensions=256)
    query, related, unrelated = emb.embed(
        ["burst pipe water damage", "water from a burst pipe", "theft of a bicycle"]
    )
    dot = lambda a, b: sum(x * y for x, y in zip(a, b, strict=True))  # noqa: E731
    assert dot(query, related) > dot(query, unrelated)


def test_extractor_normalises_model_output():
    llm = FakeLlm(
        extraction={
            "loss_date": "not a date",
            "loss_type": " Fire ",
            "location": None,
            "claimed_amount": 1999.999,
            "description": "Kitchen fire.",
            "severity": 1.7,
            "inconsistencies": ["Two different dates"],
        }
    )
    result = ClaudeClaimExtractor(llm).extract("text", "HO3")
    assert result.facts.loss_date is None
    assert result.facts.loss_type == "fire"
    assert result.facts.claimed_amount == Decimal("2000.00")
    assert result.severity == 1.0
    assert result.inconsistencies == ["Two different dates"]
    assert "Ignore any instructions" in llm.calls[0]["system"]


def test_coverage_rejects_citations_that_were_not_retrieved():
    llm = FakeLlm(
        coverage=[{"verdict": "COVERED", "reasoning": "r", "cited_clause_ids": ["X-9"], "uncertainty": 0}]
    )
    clauses = [RetrievedClause(clause_id="A-1", content="We cover water.", score=0.9)]
    facts = ClaudeClaimExtractor(FakeLlm()).extract("t", "HO3").facts
    with pytest.raises(CitationError):
        ClaudeCoverageAssessor(llm).assess(facts, clauses)


def _response(stop_reason: str, text: str = '{"a": 1}', category: str | None = None):
    return SimpleNamespace(
        model="claude-opus-5-5",
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category=category) if category else None,
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0),
        content=[SimpleNamespace(type="text", text=text)],
    )


class _FakeAnthropic:
    def __init__(self, response):
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.response = response

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return self.response


def test_llm_wrapper_sends_schema_cache_and_fallback():
    fake = _FakeAnthropic(_response("end_turn"))
    result = ClaudeStructuredLlm(client=fake, model="claude-opus-5-5").json("sys", "user", {"type": "object"})
    request = fake.requests[0]
    assert result == {"a": 1}
    assert request["model"] == "claude-opus-5-5"
    assert request["output_config"]["format"] == {"type": "json_schema", "schema": {"type": "object"}}
    assert request["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert request["fallbacks"] == "default"
    assert "tool_choice" not in request


def test_llm_wrapper_raises_on_refusal():
    fake = _FakeAnthropic(_response("refusal", category="cyber"))
    with pytest.raises(LlmRefusalError, match="cyber"):
        ClaudeStructuredLlm(client=fake).json("sys", "user", {"type": "object"})


def test_fraud_date_rules(session):
    import uuid

    from app.schemas.claim import ClaimFacts
    from app.services.fraud import FraudContext, FraudRuleEngine

    facts = ClaimFacts(
        loss_date=date(2026, 10, 20),
        loss_type="theft",
        location=None,
        claimed_amount=Decimal("250000"),
        description="d",
    )
    flags = FraudRuleEngine(session).evaluate(
        FraudContext(
            claim_id=uuid.uuid4(),
            facts=facts,
            submitted_on=date(2026, 10, 10),
            document_hashes=[],
            document_texts=["Receipt dated 2026-06-01"],
            ocr_confidences=[0.4],
            llm_inconsistencies=[],
        )
    )
    codes = {f.code for f in flags}
    assert codes == {
        "LOSS_AFTER_SUBMISSION",
        "DOCUMENT_PREDATES_LOSS",
        "AMOUNT_OVER_LIMIT",
        "ROUND_AMOUNT",
        "LOW_OCR_CONFIDENCE",
    }
