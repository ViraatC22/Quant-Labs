import os
from dataclasses import dataclass, field


def _csv_env(name: str, default: str) -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "Trading Intelligence OS API"
    app_version: str = "0.1.0"
    app_env: str = os.getenv("APP_ENV", "local")
    # The x-user-id header is a placeholder identity with no auth. It is only
    # trusted in local dev (where multi-user scoping is exercised in tests);
    # any non-local deployment must ignore it until real auth lands.
    trust_user_header: bool = _bool_env(
        "TRUST_USER_HEADER", os.getenv("APP_ENV", "local") == "local"
    )
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
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    # --- Memory / retrieval (Lattice merge) -------------------------------
    # Embeddings power semantic chunk search, entity resolution, and claim
    # dedupe. The default `local` provider is deterministic and needs no
    # network (hermetic tests, offline dev); `ollama`/`openai` are opt-in for
    # true semantics. EMBEDDING_DIM must match whatever provider is selected
    # AND the vector() column dimension in the migrations.
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "768"))
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    # Cosine thresholds. Above entity_match_threshold two node labels are the
    # same entity; the band below down to entity_review_threshold is flagged as
    # a possible duplicate rather than silently merged.
    entity_match_threshold: float = float(os.getenv("ENTITY_MATCH_THRESHOLD", "0.88"))
    entity_review_threshold: float = float(os.getenv("ENTITY_REVIEW_THRESHOLD", "0.80"))
    conflict_sim_threshold: float = float(os.getenv("CONFLICT_SIM_THRESHOLD", "0.85"))
    research_max_subqueries: int = int(os.getenv("RESEARCH_MAX_SUBQUERIES", "4"))
    cors_origins: list[str] = field(
        default_factory=lambda: _csv_env(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        )
    )


settings = Settings()
