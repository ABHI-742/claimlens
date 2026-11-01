"""Test fixtures. Database tests need Postgres with pgvector at TEST_DATABASE_URL (see README)."""

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://claimlens:claimlens@localhost:55432/claimlens_test"
)
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-at-least-32-bytes-long")

from collections.abc import Iterator  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_queue, get_storage  # noqa: E402
from app.db.base import Base, SessionLocal, engine  # noqa: E402
from app.db.init_db import init_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.job_queue import Job  # noqa: E402


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def presign_put(self, key: str, mime_type: str) -> str:
        return f"https://storage.test/put/{key}"

    def presign_get(self, key: str) -> str:
        return f"https://storage.test/get/{key}"

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def put_bytes(self, key: str, data: bytes, mime_type: str) -> None:
        self.objects[key] = data


class FakeQueue:
    def __init__(self) -> None:
        self.jobs: list[Job] = []

    def send(self, job_type: str, entity_id: str) -> None:
        self.jobs.append(Job(type=job_type, id=entity_id))

    def receive(self, max_messages: int = 5, wait_seconds: int = 20) -> list[Job]:
        return self.jobs[:max_messages]

    def delete(self, job: Job) -> None:
        self.jobs.remove(job)


class FakeLlm:
    """Returns canned JSON per schema; records every call."""

    model = "fake-claude"

    def __init__(
        self, extraction: dict[str, Any] | None = None, coverage: list[dict[str, Any]] | None = None
    ):
        self.extraction = extraction or {
            "loss_date": "2026-10-01",
            "loss_type": "Water Damage",
            "location": "12 Elm St, Fairfax VA",
            "claimed_amount": 3250.40,
            "description": "A pipe burst in the upstairs bathroom and damaged the kitchen ceiling.",
            "severity": 0.2,
            "inconsistencies": [],
        }
        self.coverage = coverage
        self.calls: list[dict[str, Any]] = []

    def json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"system": system, "user": user, "schema": schema})
        if "verdict" in schema["properties"]:
            if self.coverage:
                return self.coverage.pop(0)
            clause_ids = [part.split('"')[0] for part in user.split('<clause id="')[1:]]
            return {
                "verdict": "COVERED",
                "reasoning": "Sudden and accidental water discharge is covered.",
                "cited_clause_ids": clause_ids[:1],
                "uncertainty": 0.1,
            }
        return dict(self.extraction)


def _database_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


@pytest.fixture(scope="session")
def database() -> Iterator[None]:
    if not _database_available():
        pytest.skip(f"Postgres with pgvector not reachable at {os.environ['DATABASE_URL']}")
    Base.metadata.drop_all(engine)
    init_db(engine)
    yield


@pytest.fixture
def session(database: None) -> Iterator[Session]:
    with SessionLocal() as s:
        yield s
    with engine.begin() as conn:
        tables = [t.name for t in Base.metadata.sorted_tables if t.name not in ("users", "teams")]
        conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
def client(session: Session, storage: FakeStorage, queue: FakeQueue) -> TestClient:
    app = create_app(init_database=False)
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_queue] = lambda: queue
    return TestClient(app)


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def adjuster(client: TestClient) -> dict[str, str]:
    return login(client, "adjuster@claimlens.dev", "adjuster123")


@pytest.fixture
def supervisor(client: TestClient) -> dict[str, str]:
    return login(client, "supervisor@claimlens.dev", "supervisor123")


@pytest.fixture
def admin(client: TestClient) -> dict[str, str]:
    return login(client, "admin@claimlens.dev", "admin123")
