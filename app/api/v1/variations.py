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
        "Genera N variaciones únicas de un mensaje base usando Mistral 7B. "
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
            detail=f"No se puede conectar a Ollama: {e}",
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
    description="Verifica el estado del servicio, conexión con Ollama y modelo cargado.",
)
async def health_check(
    service: VariationService = Depends(get_service),
):
    settings = get_settings()
    health = await service.health_check()

    all_ok = health["ollama_connected"] and health["model_loaded"]

    return HealthResponse(
        status="healthy" if all_ok else "degraded",
        ollama_connected=health["ollama_connected"],
        model_loaded=health["model_loaded"],
        cache_entries=health["cache_entries"],
        version=settings.APP_VERSION,
    )


@router.get(
    "/providers",
    summary="Info del provider activo",
    description="Retorna información sobre el provider de IA configurado.",
)
async def provider_info(
    _: str = Depends(verify_api_key),
    service: VariationService = Depends(get_service),
):
    settings = get_settings()
    health = await service.health_check()

    return {
        "active_provider": f"ollama/{settings.OLLAMA_MODEL}",
        "ollama_base_url": settings.OLLAMA_BASE_URL,
        "model": settings.OLLAMA_MODEL,
        "status": "ready" if health["model_loaded"] else "not_loaded",
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
