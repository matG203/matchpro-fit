"""FastAPI application factory and scheduler lifecycle."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import catalyst_dashboard, catalyst_routes, dashboard, routes
from app.config import get_settings
from app.container import build_container
from app.db.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app(*, start_scheduler: bool = True) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        container = build_container(settings)
        app.state.container = container
        if start_scheduler:
            container.scheduler.start()
        try:
            yield
        finally:
            container.scheduler.shutdown()

    app = FastAPI(title="Earnings Radar", version="0.1.0", lifespan=lifespan)
    app.include_router(routes.router)
    app.include_router(catalyst_routes.router)
    app.include_router(dashboard.router)
    app.include_router(catalyst_dashboard.router)
    return app


app = create_app()
