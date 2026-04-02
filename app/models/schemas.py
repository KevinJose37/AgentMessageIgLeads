from pydantic import BaseModel, Field
from typing import Optional
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
        default=Tone.PROFESSIONAL,
        description="Tono del mensaje",
    )
    context: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Contexto del negocio para variaciones más relevantes (ej: 'Agencia de marketing digital especializada en e-commerce')",
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
                    "tone": "profesional",
                    "context": "Agencia de marketing digital especializada en ayudar a negocios a conseguir más clientes mediante Instagram y publicidad online.",
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
    provider: str = ""
    generation_time_seconds: float
    message: str = ""


class CommentRequest(BaseModel):
    """Request body for generating a comment reply to a post."""

    post_content: str = Field(
        ...,
        min_length=5,
        max_length=5000,
        description="Contenido del post de Instagram al que se quiere responder",
    )
    tone: Tone = Field(
        default=Tone.FRIENDLY,
        description="Tono del comentario",
    )
    rules: list[str] = Field(
        default=[],
        description="Reglas adicionales",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "post_content": "Hoy lanzamos nuestra nueva coleccion de verano. Meses de trabajo por fin dan frutos. Gracias a todo el equipo que hizo esto posible!",
                    "tone": "amigable",
                    "rules": ["No vender directamente"],
                }
            ]
        }
    }


class CommentResponse(BaseModel):
    """Response containing a single generated comment."""

    status: GenerationStatus
    comment: str = ""
    provider: str = ""
    generation_time_seconds: float
    message: str = ""


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    providers: list[dict]
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

