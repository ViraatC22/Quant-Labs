from fastapi import APIRouter

from app.api.v1 import graph, health, taxonomy, trades, vault

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(vault.router, prefix="/vault", tags=["vault"])
api_router.include_router(trades.router, prefix="/trades", tags=["trades"])
api_router.include_router(taxonomy.router, prefix="/taxonomy", tags=["taxonomy"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
