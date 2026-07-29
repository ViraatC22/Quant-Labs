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
            "gemini,groq,openrouter,cerebras,ollama,openai",
        )
    )
    ai_request_timeout_seconds: int = int(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "18"))
    ai_rate_limit_cooldown_seconds: int = int(
        os.getenv("AI_RATE_LIMIT_COOLDOWN_SECONDS", "60")
    )
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.6")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv(
        "OPENROUTER_MODEL",
        "openrouter/free",
    )
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    cerebras_api_key: str = os.getenv("CEREBRAS_API_KEY", "")
    cerebras_model: str = os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")
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
    ollama_chat_enabled: bool = _bool_env("OLLAMA_CHAT_ENABLED", False)
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "qwen3:4b")
    ollama_request_timeout_seconds: int = int(
        os.getenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "120")
    )
    # Cosine thresholds. Above entity_match_threshold two node labels are the
    # same entity; the band below down to entity_review_threshold is flagged as
    # a possible duplicate rather than silently merged.
    entity_match_threshold: float = float(os.getenv("ENTITY_MATCH_THRESHOLD", "0.88"))
    entity_review_threshold: float = float(os.getenv("ENTITY_REVIEW_THRESHOLD", "0.80"))
    conflict_sim_threshold: float = float(os.getenv("CONFLICT_SIM_THRESHOLD", "0.85"))
    research_max_subqueries: int = int(os.getenv("RESEARCH_MAX_SUBQUERIES", "4"))
    # Research answers use a configured chat model in `auto` mode, while still
    # falling back to the deterministic grounded writer when no key is present
    # or a provider response fails validation. This is intentionally separate
    # from import enrichment so enabling answers does not send every import.
    research_writer_mode: str = os.getenv("RESEARCH_WRITER_MODE", "auto").lower()
    # --- Session desk ------------------------------------------------------
    # Instruments shown on the macro desk. Symbols resolve through
    # market_data.SYMBOL_ALIASES / SYMBOL_PROXIES, so spot-metal entries are
    # served by a declared futures proxy rather than silently dropped.
    macro_desk_symbols: list[str] = field(
        default_factory=lambda: _csv_env(
            "MACRO_DESK_SYMBOLS",
            # Cross-asset by default: index futures, gold, oil, and the two
            # most-traded FX pairs. Index/commodity futures carry real volume
            # on the upstream feed, so Flow and the participation signal work
            # better on these than on FX (which has no volume) or on cash
            # indices (which have none either).
            "ES,NQ,XAUUSD,CL,EURUSD,USDJPY",
        )
    )
    # Financial Modeling Prep powers the news rail and economic calendar. With
    # no key both degrade to an explicit "unavailable" state; neither is ever
    # backfilled with invented content.
    fmp_api_key: str = os.getenv("FMP_API_KEY", "")
    # Shared secret for the TradingView alert webhook. Empty disables the
    # endpoint entirely — an unauthenticated webhook that writes trade records
    # is an open journal-pollution vector, so there is no default-open mode.
    tradingview_webhook_secret: str = os.getenv("TRADINGVIEW_WEBHOOK_SECRET", "")
    cors_origins: list[str] = field(
        default_factory=lambda: _csv_env(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        )
    )


settings = Settings()
