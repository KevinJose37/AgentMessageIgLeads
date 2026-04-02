import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.variations import router as variations_router, set_service as set_variation_service
from .api.v1.comments import router as comments_router, set_service as set_comment_service
from .config import get_settings
from .services.base_ai_service import build_provider_chain
from .services.cache_service import CacheService
from .services.variation_service import VariationService
from .services.comment_service import CommentService
from .services.providers.base import AIProvider

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared resources (providers + cache — created once, shared by all services)
# ---------------------------------------------------------------------------
_providers: list[AIProvider] = []
_cache: Optional[CacheService] = None


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _providers, _cache

    settings = get_settings()
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info(
        "Cache: %s  DB: %s",
        "enabled" if settings.CACHE_ENABLED else "disabled",
        settings.CACHE_DB_PATH,
    )

    # Build shared resources
    _providers = build_provider_chain(settings)

    _cache = None
    if settings.CACHE_ENABLED:
        _cache = CacheService(
            db_path=settings.CACHE_DB_PATH,
            ttl_hours=settings.CACHE_TTL_HOURS,
        )

    # Init services with shared providers + cache
    variation_service = VariationService(_providers, _cache, settings)
    comment_service = CommentService(_providers, _cache, settings)

    set_variation_service(variation_service)
    set_comment_service(comment_service)

    logger.info("Services initialized: variations, comments")

    yield

    logger.info("Shutting down...")
    # Only close providers once (shared)
    for provider in _providers:
        await provider.close()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Microservicio de IA para Instagram: genera variaciones de mensajes DM "
        "y comentarios naturales para posts. "
        "Usa Groq, Gemini o OpenAI con fallback automatico."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(variations_router)
app.include_router(comments_router)


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------
@app.get("/", tags=["root"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "endpoints": {
            "variations": "/api/v1/variations",
            "comments": "/api/v1/comments",
            "health": "/api/v1/health",
        },
    }
