from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import update

from app.api.routes.auth import REFRESH_COOKIE
from app.core.config import settings
from app.db.models import RefreshToken

LOGIN = {"email": "adjuster@claimlens.dev", "password": "adjuster123"}


def _refresh_with(client, token):
    client.cookies.clear()
    return client.post("/api/v1/auth/refresh", headers={"Cookie": f"{REFRESH_COOKIE}={token}"})


def test_access_token_lives_15_minutes(client):
    body = client.post("/api/v1/auth/login", json=LOGIN).json()
    claims = jwt.decode(body["access_token"], options={"verify_signature": False})
    assert claims["exp"] - claims["iat"] == settings.jwt_ttl_minutes * 60 == 900


def test_login_sets_httponly_refresh_cookie(client):
    response = client.post("/api/v1/auth/login", json=LOGIN)
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{REFRESH_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api/v1/auth" in cookie


def test_refresh_rotates_and_reuse_revokes_every_session(client, session):
    client.post("/api/v1/auth/login", json=LOGIN)
    first = client.cookies[REFRESH_COOKIE]

    rotated = _refresh_with(client, first)
    assert rotated.status_code == 200
    second = rotated.cookies[REFRESH_COOKIE]
    assert second != first
    new_access = {"Authorization": f"Bearer {rotated.json()['access_token']}"}
    assert client.get("/api/v1/claims", headers=new_access).status_code == 200

    # Replaying the used token is treated as theft: it fails and the newer token dies with it.
    assert _refresh_with(client, first).status_code == 401
    assert _refresh_with(client, second).status_code == 401


def test_expired_refresh_token_is_rejected(client, session):
    client.post("/api/v1/auth/login", json=LOGIN)
    token = client.cookies[REFRESH_COOKIE]
    session.execute(update(RefreshToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    session.commit()
    assert _refresh_with(client, token).status_code == 401


def test_logout_revokes_the_refresh_token(client):
    client.post("/api/v1/auth/login", json=LOGIN)
    token = client.cookies[REFRESH_COOKIE]
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert _refresh_with(client, token).status_code == 401


def test_refresh_without_cookie_is_rejected(client):
    assert client.post("/api/v1/auth/refresh").status_code == 401
