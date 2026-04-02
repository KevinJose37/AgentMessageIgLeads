from fastapi import APIRouter, Depends, HTTPException

from ...middleware.auth import verify_api_key
from ...models.schemas import (
    CommentRequest,
    CommentResponse,
    ErrorResponse,
)
from ...services.comment_service import CommentService

router = APIRouter(prefix="/api/v1", tags=["comments"])

# ---------------------------------------------------------------------------
# Service singleton (set from main.py lifespan)
# ---------------------------------------------------------------------------
_service: CommentService | None = None


def get_service() -> CommentService:
    if _service is None:
        raise HTTPException(status_code=503, detail="Comment service no inicializado")
    return _service


def set_service(service: CommentService):
    global _service
    _service = service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/comments",
    response_model=CommentResponse,
    responses={
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    summary="Generar comentario para un post",
    description=(
        "Lee el contenido de un post de Instagram y genera UN comentario "
        "natural y genuino. NO vende — genera engagement real."
    ),
)
async def generate_comment(
    request: CommentRequest,
    _: str = Depends(verify_api_key),
    service: CommentService = Depends(get_service),
):
    try:
        return await service.generate_comment(request)

    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="La generacion del comentario excedio el tiempo limite.",
        )
    except ConnectionError as e:
        raise HTTPException(
            status_code=502,
            detail=f"No se puede conectar al provider: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error de generacion: {str(e)}",
        )
