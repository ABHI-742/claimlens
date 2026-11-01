from fastapi import FastAPI

from app.api.routes import claims, health
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="ClaimLens API",
        version="0.1.0",
        description="AI-assisted insurance claim triage",
    )
    app.include_router(health.router)
    app.include_router(claims.router, prefix=settings.api_prefix)
    return app


app = create_app()
