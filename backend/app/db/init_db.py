"""Create the schema, the HNSW index and seed users. Safe to run repeatedly."""

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db import models
from app.db.base import Base


def init_db(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS policy_chunks_embedding_hnsw "
                "ON policy_chunks USING hnsw (embedding vector_cosine_ops)"
            )
        )
    with Session(engine) as session:
        seed_users(session, settings.seed_users)
        session.commit()


def seed_users(session: Session, spec: str) -> None:
    for entry in filter(None, (s.strip() for s in spec.split(","))):
        email, password, role, team_name = entry.split(":")
        if session.scalar(select(models.User).where(models.User.email == email)):
            continue
        team = session.scalar(select(models.Team).where(models.Team.name == team_name))
        if team is None:
            team = models.Team(name=team_name)
            session.add(team)
            session.flush()
        session.add(
            models.User(email=email, password_hash=hash_password(password), role=role, team_id=team.id)
        )
