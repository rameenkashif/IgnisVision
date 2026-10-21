from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.jobs.queue import get_queue
from app.ml.registry import load_models
from app.ws.capture import router as capture_router
from app.ws.routes import router as ws_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_models()  # refuses to start if ML_BACKEND=real fails (HANDOFF §9.2)
    await get_queue().resume_pending()  # jobs interrupted by a restart run again
    yield
    await get_queue().shutdown()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=f"{s.app_name} API",
        version=s.version,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(api_router)
    app.include_router(ws_router)
    app.include_router(capture_router)
    return app


app = create_app()
