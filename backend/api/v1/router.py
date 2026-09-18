"""Main API router that aggregates all v1 routes."""

from fastapi import APIRouter

from backend.api.v1 import currencies, assets, transactions, portfolios, tags, benchmarks, import_export, settings, gold

api_router = APIRouter()

api_router.include_router(currencies.router, prefix="/currencies", tags=["currencies"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(portfolios.router, prefix="/portfolios", tags=["portfolios"])
api_router.include_router(tags.router, prefix="/tags", tags=["tags"])
api_router.include_router(tags.category_router, prefix="/tag-categories", tags=["tag-categories"])
api_router.include_router(benchmarks.router, prefix="/benchmarks", tags=["benchmarks"])
api_router.include_router(import_export.router, prefix="/import", tags=["import"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(gold.router, prefix="/gold", tags=["gold"])
