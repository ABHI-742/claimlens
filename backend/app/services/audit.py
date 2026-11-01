import uuid

from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def record(
    session: Session,
    claim_id: uuid.UUID | None,
    actor: str,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """Append an audit event. The table is append-only; nothing updates or deletes rows."""
    session.add(AuditEvent(claim_id=claim_id, actor=actor, action=action, before=before, after=after))
