from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: str = "postgresql+psycopg://claimlens:claimlens@localhost:5432/claimlens"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    refresh_cookie_secure: bool = False  # set true behind HTTPS
    # Seed users created on first start: "email:password:ROLE:team" separated by commas
    seed_users: str = (
        "adjuster@claimlens.dev:adjuster123:ADJUSTER:Property,"
        "supervisor@claimlens.dev:supervisor123:SUPERVISOR:Property,"
        "admin@claimlens.dev:admin123:ADMIN:Property"
    )

    # AWS / LocalStack
    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = "http://localhost:4566"  # unset in real AWS
    aws_public_endpoint_url: str | None = "http://localhost:4566"  # host used in presigned URLs
    documents_bucket: str = "claimlens-documents"
    claims_queue_url: str = "http://localhost:4566/000000000000/claim-jobs"
    presign_ttl_seconds: int = 900

    # Claude
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "medium"

    # Pipeline providers
    ocr_provider: str = "tesseract"  # tesseract | textract
    embedding_provider: str = "hash"  # hash | local | bedrock
    embedding_dimensions: int = 1024
    bedrock_embedding_model: str = "amazon.titan-embed-text-v2:0"
    local_embedding_model: str = "BAAI/bge-large-en-v1.5"
    retrieval_top_k: int = 6

    # Fraud rules
    policy_limit_default: float = 100000.0
    low_ocr_confidence: float = 0.6

    # Triage weights and thresholds (docs/architecture.md, section 5)
    triage_weight_severity: float = 0.45
    triage_weight_fraud: float = 0.35
    triage_weight_uncertainty: float = 0.20
    triage_fast_track_max_score: float = 0.30
    triage_fast_track_max_amount: float = 5000.0
    triage_investigate_min_score: float = 0.65


settings = Settings()
