import json
import logging
import re
import time
from typing import Optional

from ..config import Settings
from ..models.enums import GenerationStatus
from ..models.schemas import VariationRequest, VariationResponse
from .cache_service import CacheService
from .prompt_builder import PromptBuilder
from .providers.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


class VariationService:
    """
    Core orchestrator: receives a variation request, checks cache,
    generates missing variations via Ollama, stores results, and returns.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        self.provider = OllamaProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            timeout=settings.OLLAMA_TIMEOUT,
        )

        self.cache: Optional[CacheService] = None
        if settings.CACHE_ENABLED:
            self.cache = CacheService(
                db_path=settings.CACHE_DB_PATH,
                ttl_hours=settings.CACHE_TTL_HOURS,
            )

        self.prompt_builder = PromptBuilder()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def generate_variations(
        self, request: VariationRequest
    ) -> VariationResponse:
        """Generate N variations for the given message."""
        start = time.time()
        from_cache = 0
        from_generation = 0
        all_variations: list[str] = []

        # 1️⃣ Try cache first
        if self.cache:
            cached = self.cache.get_cached_variations(
                message=request.message,
                tone=request.tone.value,
                num_requested=request.num_variations,
            )
            if cached:
                all_variations.extend(cached)
                from_cache = len(cached)
                logger.info("Cache provided %d variations", from_cache)

        # 2️⃣ Generate remaining via AI
        remaining = request.num_variations - len(all_variations)

        if remaining > 0:
            generated = await self._generate_in_batches(request, remaining)
            all_variations.extend(generated)
            from_generation = len(generated)

            # Store fresh generations in cache
            if self.cache and generated:
                self.cache.store_variations(
                    message=request.message,
                    tone=request.tone.value,
                    variations=generated,
                )

        # 3️⃣ Trim to exact requested count
        all_variations = all_variations[: request.num_variations]

        elapsed = time.time() - start

        # Determine status
        if len(all_variations) == 0:
            status = GenerationStatus.ERROR
        elif len(all_variations) < request.num_variations:
            status = GenerationStatus.PARTIAL
        elif from_cache > 0 and from_generation == 0:
            status = GenerationStatus.CACHED
        else:
            status = GenerationStatus.SUCCESS

        return VariationResponse(
            status=status,
            variations=all_variations,
            total=len(all_variations),
            from_cache=from_cache,
            from_generation=from_generation,
            provider=self.provider.name,
            generation_time_seconds=round(elapsed, 2),
            message=self._status_message(status, from_cache, from_generation),
        )

    # ------------------------------------------------------------------
    # Batch generation
    # ------------------------------------------------------------------

    async def _generate_in_batches(
        self, request: VariationRequest, count: int
    ) -> list[str]:
        """
        Split large requests into smaller batches to keep individual
        inference calls manageable on CPU.
        """
        all_generated: list[str] = []
        batch_size = self.settings.BATCH_SIZE

        while len(all_generated) < count:
            current_batch = min(batch_size, count - len(all_generated))

            system_prompt, user_prompt = self.prompt_builder.build_variation_prompt(
                message=request.message,
                num_variations=current_batch,
                tone=request.tone.value,
                rules=request.rules,
            )

            try:
                raw_response = await self.provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self.settings.TEMPERATURE,
                )

                variations = self._parse_variations(raw_response)
                all_generated.extend(variations)

                logger.info(
                    "Batch complete: requested=%d, parsed=%d, total=%d",
                    current_batch,
                    len(variations),
                    len(all_generated),
                )

            except (TimeoutError, ConnectionError) as e:
                logger.error("Provider error during batch: %s", e)
                break
            except Exception as e:
                logger.exception("Unexpected error during generation: %s", e)
                break

        return all_generated

    # ------------------------------------------------------------------
    # Response parsing (with multiple fallback strategies)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_variations(raw: str) -> list[str]:
        """
        Parse the model's raw text response into a list of variation strings.
        Handles JSON arrays, objects wrapping arrays, and numbered lists.
        """
        cleaned = raw.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()

        # --- Strategy 1: direct JSON array ---
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if v and str(v).strip()]
            if isinstance(parsed, dict):
                for key in ("variations", "messages", "results", "versiones", "data"):
                    if key in parsed and isinstance(parsed[key], list):
                        return [
                            str(v).strip()
                            for v in parsed[key]
                            if v and str(v).strip()
                        ]
        except json.JSONDecodeError:
            pass

        # --- Strategy 2: extract JSON array from surrounding text ---
        try:
            match = re.search(r"\[[\s\S]*\]", raw)
            if match:
                parsed = json.loads(match.group())
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if v and str(v).strip()]
        except json.JSONDecodeError:
            pass

        # --- Strategy 3: numbered list fallback ---
        lines = raw.strip().split("\n")
        result: list[str] = []
        for line in lines:
            line_clean = re.sub(r"^[\d]+[.\)\-]\s*", "", line.strip())
            line_clean = line_clean.strip("\"'")
            if line_clean and len(line_clean) > 10:
                result.append(line_clean)

        if result:
            logger.warning(
                "JSON parse failed — fell back to numbered-list extraction (%d items)",
                len(result),
            )

        return result

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> dict:
        ollama_ok = await self.provider.is_healthy()
        model_ok = await self.provider.is_model_loaded() if ollama_ok else False
        cache_count = self.cache.get_cache_count() if self.cache else 0

        return {
            "ollama_connected": ollama_ok,
            "model_loaded": model_ok,
            "cache_entries": cache_count,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self):
        await self.provider.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _status_message(
        status: GenerationStatus, from_cache: int, from_gen: int
    ) -> str:
        if status == GenerationStatus.CACHED:
            return (
                f"Todas las {from_cache} variaciones servidas "
                f"desde cache (con transformaciones ligeras)"
            )
        if status == GenerationStatus.PARTIAL:
            return (
                f"Generación parcial: {from_cache} del cache + "
                f"{from_gen} generadas por IA"
            )
        if status == GenerationStatus.ERROR:
            return "No se pudieron generar variaciones. Verifica que Ollama esté corriendo."
        return (
            f"Generación exitosa: {from_cache} del cache + "
            f"{from_gen} generadas por IA"
        )
