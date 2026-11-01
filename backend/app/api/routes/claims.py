from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.claim import ClaimCreate, ClaimCreated, ClaimDecision, ClaimDetail

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ClaimCreated)
def create_claim(payload: ClaimCreate) -> ClaimCreated:
    """Create a DRAFT claim and return presigned upload URLs for its documents."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Roadmap: document upload and SQS pipeline")


@router.post("/{claim_id}/submit", status_code=status.HTTP_202_ACCEPTED)
def submit_claim(claim_id: UUID) -> dict[str, str]:
    """Mark the claim SUBMITTED and enqueue it for processing."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Roadmap: document upload and SQS pipeline")


@router.get("/{claim_id}", response_model=ClaimDetail)
def get_claim(claim_id: UUID) -> ClaimDetail:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Roadmap: adjuster console")


@router.post("/{claim_id}/decision", response_model=ClaimDetail)
def decide(claim_id: UUID, decision: ClaimDecision) -> ClaimDetail:
    """Record an adjuster decision and write an audit event."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Roadmap: adjuster console")
