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
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://quant_labs:quant_labs_dev_password@localhost:5432/quant_labs",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "trading-vault")
    cors_origins: list[str] = field(
        default_factory=lambda: _csv_env(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        )
    )


settings = Settings()
