import logging
import time

from ..config import Settings
from ..models.enums import GenerationStatus
from ..models.schemas import CommentRequest, CommentResponse
from .base_ai_service import BaseAIService
from .cache_service import CacheService
from .prompt_builder import CommentPromptBuilder
from .providers.base import AIProvider

logger = logging.getLogger(__name__)


class CommentService(BaseAIService):
    """Service for generating a single natural Instagram post comment."""

    def __init__(
        self,
        providers: list[AIProvider],
        cache: CacheService | None,
        settings: Settings,
    ):
        super().__init__(providers, cache, settings)
        self.prompt_builder = CommentPromptBuilder()

    async def generate_comment(
        self, request: CommentRequest
    ) -> CommentResponse:
        """Generate one comment for the given post content."""
        start = time.time()
        self._last_error = ""

        if not self.providers:
            self._last_error = "No hay providers configurados."
            return CommentResponse(
                status=GenerationStatus.ERROR,
                comment="",
                provider="",
                generation_time_seconds=0,
                message=self._last_error,
            )

        system_prompt, user_prompt = self.prompt_builder.build_comment_prompt(
            post_content=request.post_content,
            tone=request.tone.value,
            rules=request.rules,
        )

        comment = ""
        provider_name = ""

        for provider in self.providers:
            try:
                is_healthy = await provider.is_healthy()
                if not is_healthy:
                    logger.warning("%s not healthy, trying next", provider.name)
                    continue

                provider_name = provider.name
                logger.info("Generating comment with %s", provider.name)

                raw = await provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self.settings.TEMPERATURE,
                )

                logger.info("Raw response (first 300 chars): %s", raw[:300])

                parsed = self._parse_json_array(raw)

                if parsed:
                    comment = parsed[0]  # Take the first one
                    break
                else:
                    self._last_error = (
                        f"Respuesta no parseable: {raw[:200]}"
                    )
                    logger.warning("Parse failed, trying next provider")
                    continue

            except (TimeoutError, ConnectionError) as e:
                self._last_error = f"{provider.name}: {e}"
                logger.warning("Provider %s failed: %s", provider.name, e)
                continue
            except Exception as e:
                self._last_error = f"{provider.name}: {type(e).__name__}: {e}"
                logger.exception("Unexpected error with %s", provider.name)
                continue

        elapsed = time.time() - start

        if comment:
            status = GenerationStatus.SUCCESS
            message = "Comentario generado exitosamente"
        else:
            status = GenerationStatus.ERROR
            message = f"No se pudo generar comentario. {self._last_error}"

        return CommentResponse(
            status=status,
            comment=comment,
            provider=provider_name,
            generation_time_seconds=round(elapsed, 2),
            message=message,
        )
