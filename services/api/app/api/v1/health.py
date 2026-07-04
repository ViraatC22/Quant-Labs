from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
def api_health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "api",
        "environment": settings.app_env,
        "version": settings.app_version,
    }
