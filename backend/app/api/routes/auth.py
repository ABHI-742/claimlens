from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import SessionDep
from app.core.security import create_access_token, verify_password
from app.db.models import User
from app.schemas.claim import LoginIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, session: Session = SessionDep) -> TokenOut:
    user = session.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return TokenOut(
        access_token=create_access_token(str(user.id), user.role, str(user.team_id)), role=user.role
    )
