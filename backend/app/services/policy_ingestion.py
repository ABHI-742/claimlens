"""Index policy wording for retrieval (docs/diagrams/sequence-policy-ingestion.md)."""

import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import PolicyChunk, PolicyDocument
from app.services import audit
from app.services.chunking import chunk_policy
from app.services.interfaces import EmbeddingProvider, OcrProvider
from app.services.storage import Storage

BATCH_SIZE = 64


class PolicyIngestor:
    def __init__(
        self, session: Session, storage: Storage, ocr: OcrProvider, embeddings: EmbeddingProvider
    ) -> None:
        self.session = session
        self.storage = storage
        self.ocr = ocr
        self.embeddings = embeddings

    def ingest(self, policy_id: uuid.UUID) -> int:
        policy = self.session.get(PolicyDocument, policy_id)
        if policy is None:
            raise LookupError(f"Policy document {policy_id} not found")
        policy.status = "INDEXING"
        self.session.commit()

        text = self.ocr.extract(self.storage.get_bytes(policy.s3_key), policy.mime_type).text
        chunks = chunk_policy(text, prefix=f"{policy.product}-{policy.version}".upper())

        self.session.execute(delete(PolicyChunk).where(PolicyChunk.policy_document_id == policy.id))
        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start : start + BATCH_SIZE]
            vectors = self.embeddings.embed([c.content for c in batch])
            self.session.add_all(
                PolicyChunk(
                    policy_document_id=policy.id,
                    product=policy.product,
                    clause_id=c.clause_id,
                    content=c.content,
                    embedding=v,
                )
                for c, v in zip(batch, vectors, strict=True)
            )
        policy.status = "ACTIVE"
        audit.record(
            self.session,
            None,
            "system:ingestion",
            "policy.indexed",
            after={"policy_id": str(policy.id), "chunks": len(chunks)},
        )
        self.session.commit()
        return len(chunks)
