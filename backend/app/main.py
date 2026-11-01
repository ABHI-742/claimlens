from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, claims, health, policies
from app.core.config import settings


def create_app(init_database: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if init_database:
            from app.db.base import engine
            from app.db.init_db import init_db

            init_db(engine)
        yield

    app = FastAPI(
        title="ClaimLens API",
        version="1.0.0",
        description="AI-assisted insurance claim triage",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(claims.router, prefix=settings.api_prefix)
    app.include_router(policies.router, prefix=settings.api_prefix)
    return app


app = create_app()
