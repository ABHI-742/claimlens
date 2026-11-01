"""Provider interfaces for the claim pipeline (docs/diagrams/class-diagram.md)."""

from dataclasses import dataclass
from typing import Protocol

from app.schemas.claim import ClaimFacts, CoverageAssessment


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float


@dataclass(frozen=True)
class RetrievedClause:
    clause_id: str
    content: str
    score: float


@dataclass(frozen=True)
class Extraction:
    facts: ClaimFacts
    severity: float
    inconsistencies: list[str]


class OcrProvider(Protocol):
    """Textract in AWS, Tesseract locally."""

    def extract(self, data: bytes, mime_type: str) -> OcrResult: ...


class EmbeddingProvider(Protocol):
    """Bedrock Titan in AWS, sentence-transformers or a hashing embedder locally."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ClaimExtractor(Protocol):
    """Fills the ClaimFacts schema from masked document text."""

    def extract(self, masked_text: str, product: str) -> Extraction: ...


class PolicyRetriever(Protocol):
    """Top-k cosine similarity search over policy chunks for one product."""

    def top_k(self, query: str, product: str, k: int) -> list[RetrievedClause]: ...


class CoverageAssessor(Protocol):
    """Decides whether the loss is covered, citing only retrieved clause IDs."""

    def assess(self, facts: ClaimFacts, clauses: list[RetrievedClause]) -> CoverageAssessment: ...
