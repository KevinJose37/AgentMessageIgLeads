from pydantic import BaseModel, Field
from .enums import Tone, GenerationStatus


class VariationRequest(BaseModel):
    """Request body for generating message variations."""

    message: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Mensaje base con placeholders opcionales como {nombre}, {detalle}",
    )
    num_variations: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Número de variaciones a generar (dinámico, 1-100)",
    )
    tone: Tone = Field(
        default=Tone.CASUAL,
        description="Tono del mensaje",
    )
    rules: list[str] = Field(
        default=[],
        description="Reglas adicionales para la generación",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Hola {nombre}, vi tu perfil y me llamó la atención {detalle}. Estoy trabajando en {oferta} y creo que podría interesarte.",
                    "num_variations": 10,
                    "tone": "casual",
                    "rules": ["Usar tuteo", "No mencionar precios"],
                }
            ]
        }
    }


class VariationResponse(BaseModel):
    """Response containing generated variations."""

    status: GenerationStatus
    variations: list[str]
    total: int
    from_cache: int = 0
    from_generation: int = 0
    provider: str = "ollama/mistral"
    generation_time_seconds: float
    message: str = ""


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    ollama_connected: bool
    model_loaded: bool
    cache_entries: int
    version: str


class CacheClearResponse(BaseModel):
    """Response after clearing cache."""

    cleared: bool
    entries_removed: int
    message: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    error_code: str = ""
