"""Run the extraction and coverage prompts against golden claims with the real Claude API.

Usage (costs real API credits; not run in CI):
    ANTHROPIC_API_KEY=... python -m evals.run_evals

Retrieval uses the sample policy in evals/sample_policy.py with the hashing embedder, so results reflect
the prompts and the model, not a production embedding model.
"""

import json
import sys
from pathlib import Path

from app.services.chunking import chunk_policy
from app.services.coverage import ClaudeCoverageAssessor
from app.services.embeddings import HashEmbeddings
from app.services.extraction import ClaudeClaimExtractor
from app.services.interfaces import RetrievedClause
from app.services.llm import ClaudeStructuredLlm
from app.services.pii import PiiMasker
from evals.sample_policy import POLICY_TEXT

GOLDEN = Path(__file__).with_name("golden_claims.json")


def retrieve(query: str, k: int = 6) -> list[RetrievedClause]:
    chunks = chunk_policy(POLICY_TEXT, prefix="HO3-2026")
    embeddings = HashEmbeddings()
    [q] = embeddings.embed([query])
    vectors = embeddings.embed([c.content for c in chunks])
    scored = sorted(
        ((sum(a * b for a, b in zip(q, v, strict=True)), c) for c, v in zip(chunks, vectors, strict=True)),
        key=lambda pair: pair[0],
        reverse=True,
    )
    return [RetrievedClause(clause_id=c.clause_id, content=c.content, score=s) for s, c in scored[:k]]


def check(case: dict, extraction, coverage) -> list[str]:
    expected, failures = case["expected"], []
    facts = extraction.facts
    if "loss_date" in expected and str(facts.loss_date) != expected["loss_date"]:
        failures.append(f"loss_date {facts.loss_date} != {expected['loss_date']}")
    if expected.get("loss_type_contains") and expected["loss_type_contains"] not in facts.loss_type:
        failures.append(f"loss_type {facts.loss_type!r} lacks {expected['loss_type_contains']!r}")
    if "claimed_amount" in expected and float(facts.claimed_amount or -1) != expected["claimed_amount"]:
        failures.append(f"claimed_amount {facts.claimed_amount} != {expected['claimed_amount']}")
    if "max_severity" in expected and extraction.severity > expected["max_severity"]:
        failures.append(f"severity {extraction.severity} > {expected['max_severity']}")
    if expected.get("expects_inconsistency") and not extraction.inconsistencies:
        failures.append("expected an inconsistency to be reported")
    if "verdict" in expected and coverage.verdict != expected["verdict"]:
        failures.append(f"verdict {coverage.verdict} != {expected['verdict']}")
    return failures


def main() -> int:
    llm = ClaudeStructuredLlm()
    extractor, assessor, masker = ClaudeClaimExtractor(llm), ClaudeCoverageAssessor(llm), PiiMasker()
    cases = json.loads(GOLDEN.read_text())
    passed = 0
    for case in cases:
        extraction = extractor.extract(masker.mask(case["documents"]).text, case["product"])
        query = f"{extraction.facts.loss_type}. {extraction.facts.description}"
        coverage = assessor.assess(extraction.facts, retrieve(query))
        failures = check(case, extraction, coverage)
        passed += not failures
        print(f"{'PASS' if not failures else 'FAIL'}  {case['id']}")
        for failure in failures:
            print(f"      - {failure}")
    print(f"\n{passed}/{len(cases)} passed with model {llm.model}")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
