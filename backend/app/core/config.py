from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://claimlens:claimlens@localhost:5432/claimlens"

    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = "http://localhost:4566"  # LocalStack; unset in AWS
    documents_bucket: str = "claimlens-documents"
    claims_queue_url: str = "http://localhost:4566/000000000000/claim-jobs"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"

    ocr_provider: str = "tesseract"  # tesseract | textract
    embedding_provider: str = "local"  # local | bedrock
    embedding_dimensions: int = 1024
    retrieval_top_k: int = 6

    # Triage weights and thresholds (see docs/architecture.md, section 5)
    triage_weight_severity: float = 0.45
    triage_weight_fraud: float = 0.35
    triage_weight_uncertainty: float = 0.20
    triage_fast_track_max_score: float = 0.30
    triage_fast_track_max_amount: float = 5000.0
    triage_investigate_min_score: float = 0.65


settings = Settings()
