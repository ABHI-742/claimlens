"""Login, refresh-token rotation and logout (docs/diagrams/sequence-auth-refresh.md)."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.db.models import RefreshToken, User
from app.schemas.claim import LoginIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "claimlens_refresh"
_COOKIE_PATH = f"{settings.api_prefix}/auth"


def _issue_tokens(session: Session, user: User, response: Response) -> TokenOut:
    token, token_hash = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    session.commit()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="strict",
        path=_COOKIE_PATH,
    )
    return TokenOut(
        access_token=create_access_token(str(user.id), user.role, str(user.team_id)), role=user.role
    )


def _revoke_all(session: Session, user_id: uuid.UUID) -> None:
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    session.commit()


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, response: Response, session: Session = SessionDep) -> TokenOut:
    user = session.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return _issue_tokens(session, user, response)


@router.post("/refresh", response_model=TokenOut)
def refresh(
    response: Response,
    session: Session = SessionDep,
    claimlens_refresh: str | None = Cookie(None),
) -> TokenOut:
    """Exchanges a refresh token for a new access token and a new refresh token (rotation)."""
    if not claimlens_refresh:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token")
    stored = session.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(claimlens_refresh))
        .with_for_update()
    )
    if stored is None or stored.expires_at < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token is invalid or expired")
    if stored.revoked_at is not None:
        # A token that was already used came back: assume it was stolen and end every session.
        _revoke_all(session, stored.user_id)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token is invalid or expired")

    stored.revoked_at = datetime.now(UTC)
    user = session.get(User, stored.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token is invalid or expired")
    return _issue_tokens(session, user, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session: Session = SessionDep,
    claimlens_refresh: str | None = Cookie(None),
) -> Response:
    if claimlens_refresh:
        session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == hash_refresh_token(claimlens_refresh),
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(REFRESH_COOKIE, path=_COOKIE_PATH)
    return response
