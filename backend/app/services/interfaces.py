"""Provider interfaces for the claim pipeline. Implementations are on the roadmap."""

from dataclasses import dataclass
from typing import Protocol

from app.schemas.claim import ClaimFacts, CoverageAssessment, FraudFlag


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float


@dataclass(frozen=True)
class PolicyChunk:
    clause_id: str
    content: str
    score: float


class OcrProvider(Protocol):
    """Textract in AWS, Tesseract locally."""

    def extract(self, data: bytes, mime_type: str) -> OcrResult: ...


class EmbeddingProvider(Protocol):
    """Bedrock Titan in AWS, sentence-transformers locally."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ClaimExtractor(Protocol):
    """Asks Claude to fill the ClaimFacts schema from masked document text."""

    def extract(self, masked_text: str) -> ClaimFacts: ...


class PolicyRetriever(Protocol):
    """Top-k cosine similarity search over policy_chunks (pgvector HNSW)."""

    def top_k(self, query: str, product: str, k: int) -> list[PolicyChunk]: ...


class CoverageAssessor(Protocol):
    """Asks Claude whether the loss is covered; must cite retrieved clause IDs."""

    def assess(self, facts: ClaimFacts, clauses: list[PolicyChunk]) -> CoverageAssessment: ...


class FraudRuleEngine(Protocol):
    def evaluate(self, facts: ClaimFacts, documents_text: list[str]) -> list[FraudFlag]: ...
