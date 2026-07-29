from fastapi import APIRouter

from app.api.v1 import desk, graph, health, research, taxonomy, trades, vault, webhooks

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(desk.router, prefix="/desk", tags=["desk"])
api_router.include_router(vault.router, prefix="/vault", tags=["vault"])
api_router.include_router(trades.router, prefix="/trades", tags=["trades"])
api_router.include_router(taxonomy.router, prefix="/taxonomy", tags=["taxonomy"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(research.router, prefix="/research", tags=["research"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
