"""SQS consumer that runs the claim pipeline and policy indexing (ADR-0002).

A job is deleted only after it succeeds. On failure the message becomes visible again after the
visibility timeout; after 3 receives SQS moves it to the dead-letter queue.
"""

import logging
import signal
import uuid

from app.db.base import SessionLocal, engine
from app.db.init_db import init_db
from app.services.coverage import ClaudeCoverageAssessor
from app.services.embeddings import build_embeddings
from app.services.extraction import ClaudeClaimExtractor
from app.services.job_queue import CLAIM_SUBMITTED, POLICY_UPLOADED, Job, JobQueue, SqsQueue
from app.services.llm import ClaudeStructuredLlm, LlmRefusalError
from app.services.ocr import build_ocr
from app.services.pipeline import ClaimPipeline
from app.services.policy_ingestion import PolicyIngestor
from app.services.retrieval import PgVectorRetriever
from app.services.storage import S3Storage, Storage

log = logging.getLogger("claimlens.worker")
MAX_ATTEMPTS = 3


class Worker:
    def __init__(self, queue: JobQueue, storage: Storage) -> None:
        self.queue = queue
        self.storage = storage
        self.ocr = build_ocr()
        self.embeddings = build_embeddings()
        self.llm = ClaudeStructuredLlm()
        self.running = True

    def handle(self, job: Job) -> None:
        with SessionLocal() as session:
            if job.type == CLAIM_SUBMITTED:
                pipeline = ClaimPipeline(
                    session=session,
                    storage=self.storage,
                    ocr=self.ocr,
                    extractor=ClaudeClaimExtractor(self.llm),
                    retriever=PgVectorRetriever(session, self.embeddings),
                    assessor=ClaudeCoverageAssessor(self.llm),
                    model_name=self.llm.model,
                )
                try:
                    pipeline.run(uuid.UUID(job.id))
                except LlmRefusalError as exc:
                    # Not retryable: send straight to FAILED for a human to handle.
                    pipeline.mark_failed(uuid.UUID(job.id), str(exc))
                except Exception as exc:
                    if job.attempt >= MAX_ATTEMPTS:
                        # Last attempt: record the failure; SQS moves the message to the DLQ.
                        pipeline.mark_failed(uuid.UUID(job.id), f"{type(exc).__name__}: {exc}")
                    raise
            elif job.type == POLICY_UPLOADED:
                PolicyIngestor(session, self.storage, self.ocr, self.embeddings).ingest(uuid.UUID(job.id))
            else:
                log.warning("Unknown job type %s", job.type)

    def run_forever(self) -> None:
        while self.running:
            for job in self.queue.receive():
                try:
                    self.handle(job)
                    self.queue.delete(job)
                except Exception:
                    log.exception("Job %s %s failed; it will be retried", job.type, job.id)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    init_db(engine)
    worker = Worker(SqsQueue(), S3Storage())

    def stop(*_: object) -> None:
        log.info("Shutting down after the current batch")
        worker.running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("Claim worker started")
    worker.run_forever()


if __name__ == "__main__":
    main()
