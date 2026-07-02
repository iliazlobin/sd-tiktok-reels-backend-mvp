from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from tiktok_reels.redis import close_redis
from tiktok_reels.routers import routers


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Schema is owned by Alembic (`alembic upgrade head` in CI/deploy); do NOT create_all here —
    # it races the migration step and raises DuplicateTableError ("relation ... already exists").
    yield
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(title="TikTok/Reels MVP", version="0.1.0", lifespan=lifespan)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    for router in routers:
        app.include_router(router)

    return app


app = create_app()
