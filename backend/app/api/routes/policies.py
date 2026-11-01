import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep, get_queue, get_storage, require_role
from app.db.models import PolicyDocument
from app.schemas.claim import ALLOWED_MIME_TYPES, PolicyCreate, PolicyCreated, PolicyOut
from app.services import audit
from app.services.job_queue import POLICY_UPLOADED, JobQueue
from app.services.storage import Storage

router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PolicyCreated)
def create_policy(
    payload: PolicyCreate,
    session: Session = SessionDep,
    storage: Storage = Depends(get_storage),
    user: CurrentUser = Depends(require_role("ADMIN")),
) -> PolicyCreated:
    if payload.mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unsupported file type")
    policy = PolicyDocument(
        product=payload.product.upper(),
        version=payload.version,
        mime_type=payload.mime_type,
        s3_key=f"policies/{payload.product.upper()}/{payload.version}/{uuid.uuid4()}",
    )
    session.add(policy)
    session.flush()
    audit.record(session, None, str(user.id), "policy.created", after={"policy_id": str(policy.id)})
    session.commit()
    return PolicyCreated(policy_id=policy.id, upload_url=storage.presign_put(policy.s3_key, policy.mime_type))


@router.post("/{policy_id}/index", status_code=status.HTTP_202_ACCEPTED, response_model=PolicyOut)
def index_policy(
    policy_id: uuid.UUID,
    session: Session = SessionDep,
    queue: JobQueue = Depends(get_queue),
    user: CurrentUser = Depends(require_role("ADMIN")),
) -> PolicyOut:
    policy = session.get(PolicyDocument, policy_id)
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")
    policy.status = "QUEUED"
    session.commit()
    queue.send(POLICY_UPLOADED, str(policy.id))
    return PolicyOut.model_validate(policy)


@router.get("", response_model=list[PolicyOut])
def list_policies(
    session: Session = SessionDep, user: CurrentUser = Depends(require_role("ADMIN", "SUPERVISOR"))
) -> list[PolicyOut]:
    rows = session.scalars(select(PolicyDocument).order_by(PolicyDocument.product, PolicyDocument.version))
    return [PolicyOut.model_validate(p) for p in rows]
