from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from source.api.exception_handlers import register_exception_handlers
from source.api.middleware import ApiRateLimitMiddleware, SecurityHeadersMiddleware
from source.api.protected_docs import register_protected_docs
from source.api.routers.http import router as http_router
from source.config.settings import settings
from source.db.bootstrap import seed_demo_data
from source.db.session import db_session_manager
from source.web.router import router as web_router
from source.tasks import process_due_jobs


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db_session_manager.init_models()
    async with db_session_manager.session() as session:
        await seed_demo_data(session)
    if settings.jobs.process_on_startup:
        await process_due_jobs()
    try:
        yield
    finally:
        await db_session_manager.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.names.title,
        root_path=settings.names.path,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.middleware.cors_origins,
        allow_credentials=True,
        allow_methods=settings.middleware.allow_methods,
        allow_headers=settings.middleware.allow_headers,
    )
    app.add_middleware(ApiRateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(http_router)
    app.include_router(web_router)
    app.mount("/static", StaticFiles(directory="source/web/static"), name="static")
    register_protected_docs(app)
    register_exception_handlers(app)
    return app
