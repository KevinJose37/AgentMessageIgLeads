from enum import Enum


class Tone(str, Enum):
    """Available tones for message variations."""

    CASUAL = "casual"
    PROFESSIONAL = "profesional"
    FRIENDLY = "amigable"
    DIRECT = "directo"
    ENTHUSIASTIC = "entusiasta"


class GenerationStatus(str, Enum):
    """Status of a variation generation request."""

    SUCCESS = "success"
    PARTIAL = "partial"  # Not all requested variations were generated
    CACHED = "cached"  # All variations served from cache
    ERROR = "error"
