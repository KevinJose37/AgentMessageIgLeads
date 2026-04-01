from fastapi import APIRouter, Depends, HTTPException

from ...config import Settings, get_settings
from ...middleware.auth import verify_api_key
from ...models.schemas import (
    CacheClearResponse,
    ErrorResponse,
    HealthResponse,
    VariationRequest,
    VariationResponse,
)
from ...services.variation_service import VariationService

router = APIRouter(prefix="/api/v1", tags=["variations"])

# ---------------------------------------------------------------------------
# Service singleton (initialized in lifespan)
# ---------------------------------------------------------------------------
_service: VariationService | None = None


def get_service() -> VariationService:
    if _service is None:
        raise HTTPException(status_code=503, detail="Servicio no inicializado")
    return _service


def init_service(settings: Settings):
    global _service
    _service = VariationService(settings)


async def shutdown_service():
    global _service
    if _service:
        await _service.close()
        _service = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/variations",
    response_model=VariationResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    summary="Generar variaciones de mensaje",
    description=(
        "Genera N variaciones únicas de un mensaje base usando IA (Groq/Ollama). "
        "Soporta placeholders dinámicos como {nombre}, {detalle}, etc."
    ),
)
async def generate_variations(
    request: VariationRequest,
    _: str = Depends(verify_api_key),
    service: VariationService = Depends(get_service),
):
    try:
        return await service.generate_variations(request)

    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=(
                "La inferencia del modelo excedió el tiempo límite. "
                "Intenta reducir num_variations o espera que el modelo esté "
                "completamente cargado en memoria."
            ),
        )
    except ConnectionError as e:
        raise HTTPException(
            status_code=502,
            detail=f"No se puede conectar al provider: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error de generación: {str(e)}",
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Verifica el estado del servicio y providers de IA.",
)
async def health_check(
    service: VariationService = Depends(get_service),
):
    settings = get_settings()
    health = await service.health_check()

    any_ready = any(p["connected"] and p["model_ready"] for p in health["providers"])

    return HealthResponse(
        status="healthy" if any_ready else "degraded",
        providers=health["providers"],
        cache_entries=health["cache_entries"],
        version=settings.APP_VERSION,
    )


@router.get(
    "/providers",
    summary="Info de providers configurados",
    description="Retorna la cadena de providers de IA con su estado.",
)
async def provider_info(
    _: str = Depends(verify_api_key),
    service: VariationService = Depends(get_service),
):
    settings = get_settings()
    health = await service.health_check()

    return {
        "provider_chain": health["providers"],
        "primary": health["providers"][0]["name"] if health["providers"] else "none",
        "batch_size": settings.BATCH_SIZE,
        "max_variations": settings.MAX_VARIATIONS_PER_REQUEST,
        "cache_enabled": settings.CACHE_ENABLED,
        "cache_entries": health["cache_entries"],
    }


@router.delete(
    "/cache",
    response_model=CacheClearResponse,
    summary="Limpiar cache de variaciones",
    description="Elimina todas las variaciones cacheadas.",
)
async def clear_cache(
    _: str = Depends(verify_api_key),
    service: VariationService = Depends(get_service),
):
    if service.cache is None:
        return CacheClearResponse(
            cleared=False,
            entries_removed=0,
            message="Cache está deshabilitado en la configuración.",
        )

    removed = service.cache.clear_cache()
    return CacheClearResponse(
        cleared=True,
        entries_removed=removed,
        message=f"Se eliminaron {removed} variaciones del cache.",
    )
