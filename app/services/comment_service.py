import logging
from typing import Optional

from ..config import Settings
from ..models.schemas import CommentRequest, CommentResponse
from .base_ai_service import BaseAIService
from .cache_service import CacheService
from .prompt_builder import CommentPromptBuilder
from .providers.base import AIProvider

logger = logging.getLogger(__name__)


class CommentService(BaseAIService):
    """Service for generating natural Instagram post comments."""

    def __init__(
        self,
        providers: list[AIProvider],
        cache: Optional[CacheService],
        settings: Settings,
    ):
        super().__init__(providers, cache, settings)
        self.prompt_builder = CommentPromptBuilder()

    async def generate_comments(
        self, request: CommentRequest
    ) -> CommentResponse:
        """Generate N comment replies for the given post content."""

        def build_prompt(batch_size: int) -> tuple[str, str]:
            return self.prompt_builder.build_comment_prompt(
                post_content=request.post_content,
                num_comments=batch_size,
                tone=request.tone.value,
                rules=request.rules,
                context=request.context,
            )

        result = await self._generate_with_providers(
            build_prompt_fn=build_prompt,
            count=request.num_comments,
            cache_key=request.post_content,
            cache_tone=f"comment_{request.tone.value}",
        )

        return CommentResponse(
            status=result["status"],
            comments=result["items"],
            total=result["total"],
            from_cache=result["from_cache"],
            from_generation=result["from_generation"],
            provider=result["provider"],
            generation_time_seconds=result["generation_time_seconds"],
            message=self._status_message(
                result["status"],
                result["from_cache"],
                result["from_generation"],
                result["error"],
                item_name="comentarios",
            ),
        )
