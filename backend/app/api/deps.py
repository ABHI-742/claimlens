import uuid
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.db.base import get_session
from app.services.job_queue import JobQueue, SqsQueue
from app.services.storage import S3Storage, Storage

_bearer = HTTPBearer(auto_error=False)

SessionDep = Depends(get_session)


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    role: str
    team_id: uuid.UUID


@lru_cache
def get_storage() -> Storage:
    return S3Storage()


@lru_cache
def get_queue() -> JobQueue:
    return SqsQueue()


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    return CurrentUser(id=uuid.UUID(payload["sub"]), role=payload["role"], team_id=uuid.UUID(payload["team"]))


def require_role(*roles: str) -> Callable[[CurrentUser], CurrentUser]:
    def check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {', '.join(roles)}")
        return user

    return check
