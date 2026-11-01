import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentUser, SessionDep, get_current_user, get_queue, get_storage, require_role
from app.db.models import AuditEvent, Claim, Document, PolicyChunk
from app.schemas.claim import (
    ALLOWED_MIME_TYPES,
    AuditEventOut,
    Citation,
    ClaimCreate,
    ClaimCreated,
    ClaimDecision,
    ClaimDetail,
    ClaimFacts,
    ClaimStatus,
    ClaimSummary,
    CoverageAssessment,
    DecisionType,
    DocumentOut,
    FraudFlag,
    Severity,
    TriageQueue,
    UploadTarget,
)
from app.services import audit
from app.services.job_queue import CLAIM_SUBMITTED, JobQueue
from app.services.storage import Storage

router = APIRouter(prefix="/claims", tags=["claims"])

REVIEWERS = ("ADJUSTER", "SUPERVISOR", "ADMIN")


def _load(session: Session, claim_id: uuid.UUID, user: CurrentUser) -> Claim:
    claim = session.scalar(
        select(Claim)
        .where(Claim.id == claim_id)
        .options(
            selectinload(Claim.documents),
            selectinload(Claim.facts),
            selectinload(Claim.coverage),
            selectinload(Claim.fraud_flags),
        )
    )
    # Users only see their own team's claims; 404 rather than 403 so IDs can't be probed.
    if claim is None or (user.role != "ADMIN" and claim.team_id != user.team_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    return claim


def _summary(claim: Claim) -> ClaimSummary:
    return ClaimSummary(
        id=claim.id,
        policy_number=claim.policy_number,
        product=claim.product,
        status=claim.status,
        queue=claim.queue,
        triage_score=claim.triage_score,
        submitted_at=claim.submitted_at,
        claimed_amount=claim.facts.claimed_amount if claim.facts else None,
        flag_count=len(claim.fraud_flags),
    )


def _detail(session: Session, claim: Claim) -> ClaimDetail:
    citations: list[Citation] = []
    if claim.coverage:
        rows = session.execute(
            select(PolicyChunk.clause_id, PolicyChunk.content).where(
                PolicyChunk.clause_id.in_(claim.coverage.cited_clause_ids),
                PolicyChunk.product == claim.product,
            )
        ).all()
        citations = [Citation(clause_id=r.clause_id, content=r.content) for r in rows]
    events = session.scalars(
        select(AuditEvent).where(AuditEvent.claim_id == claim.id).order_by(AuditEvent.at, AuditEvent.id)
    ).all()
    return ClaimDetail(
        **_summary(claim).model_dump(),
        severity=claim.facts.severity if claim.facts else None,
        failure_reason=claim.failure_reason,
        facts=ClaimFacts.model_validate(claim.facts) if claim.facts else None,
        inconsistencies=claim.facts.inconsistencies if claim.facts else [],
        coverage=CoverageAssessment.model_validate(claim.coverage) if claim.coverage else None,
        citations=citations,
        fraud_flags=[FraudFlag.model_validate(f) for f in claim.fraud_flags],
        documents=[DocumentOut.model_validate(d) for d in claim.documents],
        audit=[AuditEventOut.model_validate(e) for e in events],
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ClaimCreated)
def create_claim(
    payload: ClaimCreate,
    session: Session = SessionDep,
    storage: Storage = Depends(get_storage),
    user: CurrentUser = Depends(get_current_user),
) -> ClaimCreated:
    """Create a DRAFT claim and return presigned upload URLs for its documents."""
    bad = [d.mime_type for d in payload.documents if d.mime_type not in ALLOWED_MIME_TYPES]
    if bad:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unsupported file types: {sorted(set(bad))}"
        )

    claim = Claim(
        policy_number=payload.policy_number.upper(),
        product=payload.product.upper(),
        team_id=user.team_id,
        created_by=str(user.id),
    )
    session.add(claim)
    session.flush()
    uploads = []
    for doc_in in payload.documents:
        doc = Document(
            claim_id=claim.id,
            filename=doc_in.filename,
            mime_type=doc_in.mime_type,
            s3_key=f"claims/{claim.id}/{uuid.uuid4()}-{doc_in.filename}",
        )
        session.add(doc)
        session.flush()
        uploads.append(
            UploadTarget(
                document_id=doc.id,
                filename=doc.filename,
                upload_url=storage.presign_put(doc.s3_key, doc.mime_type),
            )
        )
    audit.record(session, claim.id, str(user.id), "claim.created", after={"documents": len(uploads)})
    session.commit()
    return ClaimCreated(claim_id=claim.id, uploads=uploads)


@router.post("/{claim_id}/submit", status_code=status.HTTP_202_ACCEPTED, response_model=ClaimSummary)
def submit_claim(
    claim_id: uuid.UUID,
    session: Session = SessionDep,
    queue: JobQueue = Depends(get_queue),
    user: CurrentUser = Depends(get_current_user),
) -> ClaimSummary:
    """Mark the claim SUBMITTED and enqueue it for processing."""
    claim = _load(session, claim_id, user)
    if claim.status not in (ClaimStatus.DRAFT, ClaimStatus.AWAITING_INFO, ClaimStatus.FAILED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Claim is {claim.status}")
    if claim.status == ClaimStatus.FAILED and user.role != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an admin can requeue a failed claim")
    before = {"status": claim.status}
    claim.status = ClaimStatus.SUBMITTED
    claim.submitted_at = claim.submitted_at or datetime.now(UTC)
    audit.record(
        session, claim.id, str(user.id), "claim.submitted", before=before, after={"status": claim.status}
    )
    session.commit()
    queue.send(CLAIM_SUBMITTED, str(claim.id))
    return _summary(claim)


@router.get("", response_model=list[ClaimSummary])
def list_claims(
    queue: TriageQueue | None = None,
    claim_status: ClaimStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = SessionDep,
    user: CurrentUser = Depends(require_role(*REVIEWERS)),
) -> list[ClaimSummary]:
    query = (
        select(Claim)
        .options(selectinload(Claim.facts), selectinload(Claim.fraud_flags))
        .order_by(Claim.triage_score.desc().nulls_last(), Claim.submitted_at)
        .limit(limit)
    )
    if user.role != "ADMIN":
        query = query.where(Claim.team_id == user.team_id)
    if queue:
        query = query.where(Claim.queue == queue)
    if claim_status:
        query = query.where(Claim.status == claim_status)
    return [_summary(c) for c in session.scalars(query).all()]


@router.get("/{claim_id}", response_model=ClaimDetail)
def get_claim(
    claim_id: uuid.UUID, session: Session = SessionDep, user: CurrentUser = Depends(get_current_user)
) -> ClaimDetail:
    return _detail(session, _load(session, claim_id, user))


@router.get("/{claim_id}/documents/{document_id}/url")
def document_url(
    claim_id: uuid.UUID,
    document_id: uuid.UUID,
    session: Session = SessionDep,
    storage: Storage = Depends(get_storage),
    user: CurrentUser = Depends(require_role(*REVIEWERS)),
) -> dict[str, str]:
    claim = _load(session, claim_id, user)
    doc = next((d for d in claim.documents if d.id == document_id), None)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    audit.record(session, claim.id, str(user.id), "document.viewed", after={"document_id": str(doc.id)})
    session.commit()
    return {"url": storage.presign_get(doc.s3_key)}


@router.post("/{claim_id}/decision", response_model=ClaimDetail)
def decide(
    claim_id: uuid.UUID,
    payload: ClaimDecision,
    session: Session = SessionDep,
    user: CurrentUser = Depends(require_role(*REVIEWERS)),
) -> ClaimDetail:
    """Record an adjuster decision and write an audit event (docs/diagrams/state-claim-lifecycle.md)."""
    claim = _load(session, claim_id, user)
    if claim.status != ClaimStatus.READY_FOR_REVIEW:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Claim is {claim.status}, not READY_FOR_REVIEW")

    high_flags = any(f.severity == Severity.HIGH for f in claim.fraud_flags)
    if payload.decision == DecisionType.DENY and user.role == "ADJUSTER":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Denials need supervisor sign-off")
    if payload.decision == DecisionType.APPROVE and high_flags and user.role == "ADJUSTER":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Claims with high-severity fraud flags need a supervisor"
        )

    before = {"status": claim.status, "queue": claim.queue}
    if payload.decision == DecisionType.APPROVE:
        claim.status = ClaimStatus.APPROVED
    elif payload.decision == DecisionType.DENY:
        claim.status = ClaimStatus.DENIED
    elif payload.decision == DecisionType.REQUEST_INFO:
        claim.status = ClaimStatus.AWAITING_INFO
    else:
        claim.queue = TriageQueue.INVESTIGATE
    audit.record(
        session,
        claim.id,
        str(user.id),
        f"decision.{payload.decision.lower()}",
        before=before,
        after={"status": claim.status, "queue": claim.queue, "note": payload.note},
    )
    session.commit()
    return _detail(session, claim)
