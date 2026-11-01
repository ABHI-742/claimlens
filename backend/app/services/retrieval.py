"""pgvector retrieval over policy chunks (ADR-0001)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PolicyChunk, PolicyDocument
from app.services.interfaces import EmbeddingProvider, RetrievedClause


class PgVectorRetriever:
    def __init__(self, session: Session, embeddings: EmbeddingProvider) -> None:
        self.session = session
        self.embeddings = embeddings

    def top_k(self, query: str, product: str, k: int) -> list[RetrievedClause]:
        [query_vector] = self.embeddings.embed([query])
        distance = PolicyChunk.embedding.cosine_distance(query_vector)
        rows = self.session.execute(
            select(PolicyChunk.clause_id, PolicyChunk.content, distance.label("distance"))
            .join(PolicyDocument, PolicyDocument.id == PolicyChunk.policy_document_id)
            .where(PolicyChunk.product == product, PolicyDocument.status == "ACTIVE")
            .order_by(distance)
            .limit(k)
        ).all()
        return [RetrievedClause(clause_id=r.clause_id, content=r.content, score=1 - r.distance) for r in rows]
