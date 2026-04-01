import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.variations import (
    init_service,
    router as variations_router,
    shutdown_service,
)
from .config import get_settings

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
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("Ollama: %s  Model: %s", settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL)
    logger.info("Cache: %s  DB: %s", "enabled" if settings.CACHE_ENABLED else "disabled", settings.CACHE_DB_PATH)

    init_service(settings)

    yield

    logger.info("Shutting down…")
    await shutdown_service()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Microservicio de generación de variaciones de texto para mensajes de Instagram. "
        "Usa Mistral 7B (via Ollama) para reescribir un mensaje base en múltiples "
        "variaciones naturales que no parezcan enviadas por un bot."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allows Chrome extension (chrome-extension://*) and any origin
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


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------
@app.get("/", tags=["root"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
