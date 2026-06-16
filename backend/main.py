"""FastAPI application entry point."""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.database import init_db, SessionLocal
from backend.limiter import limiter
from backend.routers import auth as auth_router
from backend.routers import admin as admin_router
from backend.routers import chat, documents, feedback, metrics, sessions
from backend import runtime_settings

log = logging.getLogger(__name__)


class _Settings(BaseSettings):
    allowed_origins: str = "http://localhost:5173"
    env: str = "development"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


_settings = _Settings()


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom 429 body used by both the @limiter.limit() path and SlowAPIMiddleware."""
    current_limit = getattr(request.state, "view_rate_limit", None)
    if current_limit is not None:
        _, reset_time = current_limit
        retry_after = max(1, int(reset_time - time.time()))
    else:
        retry_after = 60
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded. Try again in {retry_after} seconds.",
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _settings.env == "development":
        log.info("DEV: running init_db() fallback (prefer `alembic upgrade head`)")
        await init_db()
    # Load persisted settings from DB into memory
    async with SessionLocal() as db:
        await runtime_settings.load_from_db(db)
    try:
        await asyncio.to_thread(chat._get_pipeline)
        log.info("Pipeline pre-warmed successfully")
    except Exception as e:
        log.warning(f"Pipeline pre-warm failed ({e}); will retry on first request")
    yield


app = FastAPI(
    title="Agentic RAG API",
    description="Chat, sessions, metrics and feedback for the Agentic RAG knowledge base.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Rate limiting ──────────────────────────────────────────────────────────────
# Register the custom handler on both layers:
#   • app.state.limiter._rate_limit_exceeded_handler → used by SlowAPIMiddleware
#     when enforcing default_limits (no decorator on the route)
#   • app.add_exception_handler → used when @limiter.limit() raises the exception
app.state.limiter = limiter
limiter._rate_limit_exceeded_handler = _rate_limit_handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

# SlowAPIMiddleware must be added FIRST so that CORSMiddleware (added second) is
# the outermost wrapper. Starlette builds the stack in reverse add-order, meaning
# the last add_middleware call is the first to process each request. CORS must run
# before rate limiting so browser pre-flight OPTIONS requests are never throttled.
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_V1 = "/api/v1"

app.include_router(auth_router.router, prefix=_V1)
app.include_router(chat.router, prefix=_V1)
app.include_router(sessions.router, prefix=_V1)
app.include_router(feedback.router, prefix=_V1)
app.include_router(metrics.router, prefix=_V1)
app.include_router(documents.router, prefix=_V1)
app.include_router(admin_router.router, prefix=_V1)


@app.get("/health")
async def health():
    return {"status": "ok"}
