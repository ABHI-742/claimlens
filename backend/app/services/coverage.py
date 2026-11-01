"""Coverage assessment grounded in retrieved policy clauses (RAG)."""

from app.schemas.claim import ClaimFacts, CoverageAssessment, CoverageVerdict
from app.services.interfaces import RetrievedClause
from app.services.llm import StructuredLlm

SYSTEM_PROMPT = """You are a coverage analyst at a property and casualty insurer.
Given the facts of a claim and excerpts from the policy wording, decide whether the loss appears to be covered.

Rules:
- Base your answer only on the policy clauses provided. Do not rely on general knowledge of insurance.
- Cite every clause you relied on by its clause_id, exactly as given. Cite at least one clause.
- Check exclusions and conditions as carefully as insuring agreements.
- verdict is COVERED, NOT_COVERED or UNCLEAR. Use UNCLEAR when the clauses do not settle the question
  or key facts are missing.
- uncertainty is a number from 0 (certain) to 1 (no basis for a decision).
- reasoning is three to six sentences an adjuster can verify against the cited clauses.
- You are recommending, not deciding. A human adjuster makes the final decision."""

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["COVERED", "NOT_COVERED", "UNCLEAR"]},
        "reasoning": {"type": "string"},
        "cited_clause_ids": {"type": "array", "items": {"type": "string"}},
        "uncertainty": {"type": "number"},
    },
    "required": ["verdict", "reasoning", "cited_clause_ids", "uncertainty"],
    "additionalProperties": False,
}


class CitationError(ValueError):
    """The model cited a clause that was not retrieved."""


class ClaudeCoverageAssessor:
    def __init__(self, llm: StructuredLlm) -> None:
        self.llm = llm

    def assess(self, facts: ClaimFacts, clauses: list[RetrievedClause]) -> CoverageAssessment:
        if not clauses:
            return CoverageAssessment(
                verdict=CoverageVerdict.UNCLEAR,
                reasoning="No policy wording is indexed for this product, so coverage could not be assessed.",
                cited_clause_ids=["NONE"],
                uncertainty=1.0,
            )

        clause_text = "\n\n".join(f'<clause id="{c.clause_id}">\n{c.content}\n</clause>' for c in clauses)
        user = f"<claim_facts>\n{facts.model_dump_json(indent=2)}\n</claim_facts>\n\n<policy>\n{clause_text}\n</policy>"
        data = self.llm.json(SYSTEM_PROMPT, user, SCHEMA)

        allowed = {c.clause_id for c in clauses}
        cited = [cid for cid in data["cited_clause_ids"] if cid in allowed]
        unknown = set(data["cited_clause_ids"]) - allowed
        if unknown or not cited:
            raise CitationError(
                f"Assessment cited clauses that were not retrieved: {sorted(unknown) or 'none'}"
            )

        return CoverageAssessment(
            verdict=CoverageVerdict(data["verdict"]),
            reasoning=data["reasoning"],
            cited_clause_ids=cited,
            uncertainty=min(max(float(data["uncertainty"]), 0.0), 1.0),
        )
