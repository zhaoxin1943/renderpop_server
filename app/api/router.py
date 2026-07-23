from fastapi import APIRouter

from app.api.routes import (
    assets,
    auth,
    billing,
    creation_sessions,
    dance,
    dev,
    generations,
    health,
    me,
    showcase,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(generations.router)
api_router.include_router(creation_sessions.router)
api_router.include_router(dance.router)
api_router.include_router(assets.router)
api_router.include_router(showcase.router)
api_router.include_router(billing.router)
api_router.include_router(webhooks.router)
api_router.include_router(dev.router)
