from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader
from ..config import get_settings

# Header name the Chrome extension must include
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str = Security(API_KEY_HEADER),
) -> str:
    """
    Dependency that validates the X-API-Key header.
    Raises 401 if missing, 403 if invalid.
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key requerida. Incluye el header X-API-Key.",
        )

    settings = get_settings()

    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=403,
            detail="API key inválida.",
        )

    return api_key
