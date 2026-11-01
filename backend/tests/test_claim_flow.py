"""End-to-end flow through the API, worker and pipeline (Claude replaced by FakeLlm)."""

from tests.conftest import FakeLlm, login
from tests.factories import CLAIM_TEXT, index_policy, make_worker, process_all, submit_claim


def test_submitted_claim_is_processed_and_fast_tracked(client, session, storage, queue, adjuster, admin):
    index_policy(session, client, admin, storage, queue)
    claim_id = submit_claim(client, adjuster, storage)
    assert [j.type for j in queue.jobs] == ["claim.submitted"]

    llm = FakeLlm()
    process_all(make_worker(queue, storage, llm), queue)

    detail = client.get(f"/api/v1/claims/{claim_id}", headers=adjuster).json()
    assert detail["status"] == "READY_FOR_REVIEW"
    assert detail["queue"] == "FAST_TRACK"
    assert detail["facts"]["loss_type"] == "water damage"
    assert detail["facts"]["claimed_amount"] == "3250.40"
    assert detail["coverage"]["verdict"] == "COVERED"
    assert detail["citations"] and detail["citations"][0]["clause_id"].startswith("HO3-2026-")
    assert [e["action"] for e in detail["audit"]] == [
        "claim.created",
        "claim.submitted",
        "processing.started",
        "processing.completed",
    ]


def test_pii_never_reaches_the_model(client, session, storage, queue, adjuster, admin):
    index_policy(session, client, admin, storage, queue)
    submit_claim(client, adjuster, storage)
    llm = FakeLlm()
    process_all(make_worker(queue, storage, llm), queue)

    prompts = " ".join(call["user"] for call in llm.calls)
    assert "123-45-6789" not in prompts
    assert "703-555-0142" not in prompts
    assert "[SSN_1]" in prompts


def test_retrieval_puts_the_water_clause_in_front_of_the_model(
    client, session, storage, queue, adjuster, admin
):
    index_policy(session, client, admin, storage, queue)
    submit_claim(client, adjuster, storage)
    llm = FakeLlm()
    process_all(make_worker(queue, storage, llm), queue)

    coverage_prompt = next(c["user"] for c in llm.calls if "verdict" in c["schema"]["properties"])
    first_clause = coverage_prompt.split("<clause", 2)[1]
    assert "burst pipe" in first_clause


def test_duplicate_document_sends_second_claim_to_investigation(
    client, session, storage, queue, adjuster, admin
):
    index_policy(session, client, admin, storage, queue)
    submit_claim(client, adjuster, storage)
    second = submit_claim(client, adjuster, storage, text=CLAIM_TEXT, policy_number="HO3-99999")
    process_all(make_worker(queue, storage, FakeLlm()), queue)

    detail = client.get(f"/api/v1/claims/{second}", headers=adjuster).json()
    assert detail["queue"] == "INVESTIGATE"
    assert "DUPLICATE_DOCUMENT" in [f["code"] for f in detail["fraud_flags"]]


def test_invalid_citation_is_retried_once(client, session, storage, queue, adjuster, admin):
    index_policy(session, client, admin, storage, queue)
    claim_id = submit_claim(client, adjuster, storage)
    llm = FakeLlm(
        coverage=[
            {"verdict": "COVERED", "reasoning": "x", "cited_clause_ids": ["MADE-UP"], "uncertainty": 0.1},
        ]
    )
    process_all(make_worker(queue, storage, llm), queue)

    detail = client.get(f"/api/v1/claims/{claim_id}", headers=adjuster).json()
    assert detail["status"] == "READY_FOR_REVIEW"
    assert sum("verdict" in c["schema"]["properties"] for c in llm.calls) == 2


def test_no_policy_indexed_gives_unclear_coverage(client, session, storage, queue, adjuster):
    claim_id = submit_claim(client, adjuster, storage)
    process_all(make_worker(queue, storage, FakeLlm()), queue)

    detail = client.get(f"/api/v1/claims/{claim_id}", headers=adjuster).json()
    assert detail["coverage"]["verdict"] == "UNCLEAR"
    assert detail["queue"] == "STANDARD"


def test_reprocessing_is_idempotent(client, session, storage, queue, adjuster, admin):
    index_policy(session, client, admin, storage, queue)
    claim_id = submit_claim(client, adjuster, storage)
    worker = make_worker(queue, storage, FakeLlm())
    job = queue.jobs[0]
    worker.handle(job)
    worker.handle(job)  # SQS delivered the same message twice

    detail = client.get(f"/api/v1/claims/{claim_id}", headers=adjuster).json()
    assert detail["status"] == "READY_FOR_REVIEW"
    assert [e["action"] for e in detail["audit"]].count("processing.completed") == 1


def test_review_decisions_and_role_rules(client, session, storage, queue, adjuster, supervisor, admin):
    index_policy(session, client, admin, storage, queue)
    claim_id = submit_claim(client, adjuster, storage)
    process_all(make_worker(queue, storage, FakeLlm()), queue)

    queue_list = client.get("/api/v1/claims?queue=FAST_TRACK", headers=adjuster).json()
    assert [c["id"] for c in queue_list] == [claim_id]

    deny = client.post(
        f"/api/v1/claims/{claim_id}/decision", json={"decision": "DENY", "note": "no"}, headers=adjuster
    )
    assert deny.status_code == 403

    approve = client.post(
        f"/api/v1/claims/{claim_id}/decision",
        json={"decision": "APPROVE", "note": "Plumber invoice checks out"},
        headers=adjuster,
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "APPROVED"
    assert approve.json()["audit"][-1]["action"] == "decision.approve"

    again = client.post(
        f"/api/v1/claims/{claim_id}/decision", json={"decision": "APPROVE", "note": "x"}, headers=supervisor
    )
    assert again.status_code == 409


def test_other_teams_cannot_see_claims(client, session, storage, queue, adjuster):
    from app.db.init_db import seed_users

    seed_users(session, "auto@claimlens.dev:auto12345:ADJUSTER:Auto")
    session.commit()
    claim_id = submit_claim(client, adjuster, storage)
    other = login(client, "auto@claimlens.dev", "auto12345")

    assert client.get(f"/api/v1/claims/{claim_id}", headers=other).status_code == 404
    assert client.get("/api/v1/claims", headers=other).json() == []


def test_requires_authentication(client):
    assert client.get("/api/v1/claims").status_code == 401
    bad = client.post("/api/v1/auth/login", json={"email": "adjuster@claimlens.dev", "password": "wrong"})
    assert bad.status_code == 401


def test_rejects_unsupported_file_types(client, adjuster):
    response = client.post(
        "/api/v1/claims",
        json={
            "policy_number": "HO3-1",
            "product": "HO3",
            "documents": [{"filename": "x.exe", "mime_type": "application/x-msdownload"}],
        },
        headers=adjuster,
    )
    assert response.status_code == 422
