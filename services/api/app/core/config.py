import os
from dataclasses import dataclass, field


def _csv_env(name: str, default: str) -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = "Trading Intelligence OS API"
    app_version: str = "0.1.0"
    app_env: str = os.getenv("APP_ENV", "local")
    # Local dev/test default to SQLite so the API runs without Docker/Postgres.
    # docker-compose and production set DATABASE_URL explicitly to PostgreSQL.
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./quant_labs_dev.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "trading-vault")
    # Cloud AI is opt-in because vault records can contain private trading notes.
    # Set AI_ENRICHMENT_MODE=auto plus at least one provider key to send import
    # text to the first available provider in AI_PROVIDER_ORDER.
    ai_enrichment_mode: str = os.getenv("AI_ENRICHMENT_MODE", "local").lower()
    ai_provider_order: list[str] = field(
        default_factory=lambda: _csv_env(
            "AI_PROVIDER_ORDER",
            "openrouter,groq,gemini,cerebras",
        )
    )
    ai_request_timeout_seconds: int = int(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "18"))
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv(
        "OPENROUTER_MODEL",
        "mistralai/mistral-small-3.2-24b-instruct:free",
    )
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    cerebras_api_key: str = os.getenv("CEREBRAS_API_KEY", "")
    cerebras_model: str = os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")
    cors_origins: list[str] = field(
        default_factory=lambda: _csv_env(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        )
    )


settings = Settings()
