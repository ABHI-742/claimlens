from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.embeddings import HashEmbeddings
from app.services.job_queue import CLAIM_SUBMITTED, POLICY_UPLOADED
from app.services.ocr import OcrRouter
from app.services.policy_ingestion import PolicyIngestor
from app.workers.claim_worker import Worker
from evals.sample_policy import POLICY_TEXT
from tests.conftest import FakeLlm, FakeQueue, FakeStorage

CLAIM_TEXT = """Claim form - policy HO3-55821
Insured: Jane Doe, SSN 123-45-6789, phone 703-555-0142
On 2026-10-01 a pipe burst in the upstairs bathroom at 12 Elm St, Fairfax VA.
Water came through the kitchen ceiling. Plumber invoice dated 2026-10-02: $3,250.40.
"""


class NoOcr:
    def extract(self, data: bytes, mime_type: str):  # pragma: no cover - text files never reach it
        raise AssertionError("OCR should not run for text/plain files")


def index_policy(
    session: Session, client: TestClient, admin: dict, storage: FakeStorage, queue: FakeQueue
) -> str:
    created = client.post(
        "/api/v1/policies",
        json={"product": "HO3", "version": "2026", "mime_type": "text/plain"},
        headers=admin,
    ).json()
    from app.db.models import PolicyDocument

    policy = session.get(PolicyDocument, created["policy_id"])
    storage.put_bytes(policy.s3_key, POLICY_TEXT.encode(), "text/plain")
    client.post(f"/api/v1/policies/{created['policy_id']}/index", headers=admin)
    job = next(j for j in queue.jobs if j.type == POLICY_UPLOADED)
    PolicyIngestor(session, storage, OcrRouter(NoOcr()), HashEmbeddings()).ingest(policy.id)
    queue.delete(job)
    return created["policy_id"]


def submit_claim(
    client: TestClient,
    headers: dict,
    storage: FakeStorage,
    text: str = CLAIM_TEXT,
    policy_number: str = "HO3-55821",
) -> str:
    created = client.post(
        "/api/v1/claims",
        json={
            "policy_number": policy_number,
            "product": "HO3",
            "documents": [{"filename": "claim.txt", "mime_type": "text/plain"}],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    key = body["uploads"][0]["upload_url"].split("/put/", 1)[1]
    storage.put_bytes(key, text.encode(), "text/plain")
    submitted = client.post(f"/api/v1/claims/{body['claim_id']}/submit", headers=headers)
    assert submitted.status_code == 202, submitted.text
    return body["claim_id"]


def make_worker(queue: FakeQueue, storage: FakeStorage, llm: FakeLlm) -> Worker:
    worker = Worker.__new__(Worker)
    worker.queue = queue
    worker.storage = storage
    worker.ocr = OcrRouter(NoOcr())
    worker.embeddings = HashEmbeddings()
    worker.llm = llm
    worker.running = True
    return worker


def process_all(worker: Worker, queue: FakeQueue) -> None:
    for job in [j for j in queue.jobs if j.type == CLAIM_SUBMITTED]:
        worker.handle(job)
        queue.delete(job)
