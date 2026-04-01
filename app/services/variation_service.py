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
from .providers.base import AIProvider
from .providers.groq_provider import OpenAICompatibleProvider
from .providers.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)


class VariationService:
    """
    Core orchestrator: receives a variation request, checks cache,
    generates missing variations via AI providers (with fallback),
    stores results, and returns.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._last_error: str = ""
        self._active_provider_name: str = ""

        # Build provider chain (primary → fallbacks)
        self.providers: list[AIProvider] = self._build_provider_chain(settings)

        if not self.providers:
            logger.error(
                "No AI providers configured! Set at least one API key in .env "
                "(GROQ_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY)"
            )

        self.cache: Optional[CacheService] = None
        if settings.CACHE_ENABLED:
            self.cache = CacheService(
                db_path=settings.CACHE_DB_PATH,
                ttl_hours=settings.CACHE_TTL_HOURS,
            )

        self.prompt_builder = PromptBuilder()

    # ------------------------------------------------------------------
    # Provider chain
    # ------------------------------------------------------------------

    @staticmethod
    def _build_provider_chain(settings: Settings) -> list[AIProvider]:
        """
        Build ordered list of providers. First available wins.
        Add an API key in .env to activate any provider.

        Chain order: Groq → Gemini → OpenAI
        """
        providers: list[AIProvider] = []

        # 1. Groq (primary — free, ultra fast)
        if settings.GROQ_API_KEY:
            providers.append(
                OpenAICompatibleProvider(
                    api_key=settings.GROQ_API_KEY,
                    model=settings.GROQ_MODEL,
                    base_url="https://api.groq.com/openai/v1",
                    provider_name="groq",
                    timeout=settings.GROQ_TIMEOUT,
                )
            )
            logger.info("Provider registered: groq/%s", settings.GROQ_MODEL)

        # 2. Google Gemini (fallback — free tier generous)
        if settings.GEMINI_API_KEY:
            providers.append(
                GeminiProvider(
                    api_key=settings.GEMINI_API_KEY,
                    model=settings.GEMINI_MODEL,
                    timeout=settings.GEMINI_TIMEOUT,
                )
            )
            logger.info("Provider registered: gemini/%s", settings.GEMINI_MODEL)

        # 3. OpenAI (fallback — paid but excellent quality)
        if settings.OPENAI_API_KEY:
            providers.append(
                OpenAICompatibleProvider(
                    api_key=settings.OPENAI_API_KEY,
                    model=settings.OPENAI_MODEL,
                    base_url="https://api.openai.com/v1",
                    provider_name="openai",
                    timeout=settings.OPENAI_TIMEOUT,
                )
            )
            logger.info("Provider registered: openai/%s", settings.OPENAI_MODEL)

        if providers:
            logger.info(
                "Provider chain: %s",
                " → ".join(p.name for p in providers),
            )

        return providers

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def generate_variations(
        self, request: VariationRequest
    ) -> VariationResponse:
        """Generate N variations for the given message."""
        start = time.time()
        self._last_error = ""
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
            provider=self._active_provider_name,
            generation_time_seconds=round(elapsed, 2),
            message=self._status_message(
                status, from_cache, from_generation, self._last_error
            ),
        )

    # ------------------------------------------------------------------
    # Batch generation with provider fallback
    # ------------------------------------------------------------------

    async def _generate_in_batches(
        self, request: VariationRequest, count: int
    ) -> list[str]:
        """
        Generate variations using the provider chain.
        If primary provider fails, falls back to the next one.
        """
        if not self.providers:
            self._last_error = "No hay providers de IA configurados. Configura GROQ_API_KEY en .env"
            return []

        all_generated: list[str] = []
        batch_size = self.settings.BATCH_SIZE
        empty_retries = 0
        max_empty_retries = 2

        # Try each provider in order
        for provider in self.providers:
            try:
                # Quick health check
                is_healthy = await provider.is_healthy()
                if not is_healthy:
                    logger.warning("Provider %s is not healthy, trying next", provider.name)
                    continue

                self._active_provider_name = provider.name
                logger.info("Using provider: %s", provider.name)

                # Generate in batches with this provider
                while len(all_generated) < count:
                    current_batch = min(batch_size, count - len(all_generated))

                    system_prompt, user_prompt = (
                        self.prompt_builder.build_variation_prompt(
                            message=request.message,
                            num_variations=current_batch,
                            tone=request.tone.value,
                            rules=request.rules,
                            context=request.context,
                        )
                    )

                    raw_response = await provider.generate(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=self.settings.TEMPERATURE,
                    )

                    logger.info(
                        "Raw response (first 300 chars): %s", raw_response[:300]
                    )

                    variations = self._parse_variations(raw_response)

                    if not variations:
                        empty_retries += 1
                        logger.warning(
                            "Parse returned 0 variations (attempt %d/%d). Raw: %s",
                            empty_retries,
                            max_empty_retries,
                            raw_response[:300],
                        )
                        if empty_retries >= max_empty_retries:
                            self._last_error = (
                                f"El modelo respondió pero no se pudo parsear. "
                                f"Respuesta: {raw_response[:200]}"
                            )
                            break
                        continue

                    all_generated.extend(variations)
                    empty_retries = 0

                    logger.info(
                        "Batch complete: requested=%d, parsed=%d, total=%d/%d",
                        current_batch,
                        len(variations),
                        len(all_generated),
                        count,
                    )

                # If we got results from this provider, stop trying others
                if all_generated:
                    break

            except (TimeoutError, ConnectionError) as e:
                logger.warning(
                    "Provider %s failed: %s — trying next provider",
                    provider.name,
                    e,
                )
                self._last_error = f"{provider.name}: {e}"
                continue
            except Exception as e:
                logger.exception(
                    "Unexpected error with %s: %s", provider.name, e
                )
                self._last_error = f"{provider.name}: {type(e).__name__}: {e}"
                continue

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
                for key in (
                    "variations", "messages", "results",
                    "versiones", "data", "versions",
                ):
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
        provider_statuses = []

        for provider in self.providers:
            healthy = await provider.is_healthy()
            model_ready = await provider.is_model_loaded() if healthy else False
            provider_statuses.append({
                "name": provider.name,
                "connected": healthy,
                "model_ready": model_ready,
            })

        cache_count = self.cache.get_cache_count() if self.cache else 0

        return {
            "providers": provider_statuses,
            "cache_entries": cache_count,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self):
        for provider in self.providers:
            await provider.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _status_message(
        status: GenerationStatus,
        from_cache: int,
        from_gen: int,
        error: str = "",
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
            base = "No se pudieron generar variaciones."
            if error:
                return f"{base} Detalle: {error}"
            return f"{base} Verifica la configuración del provider."
        return (
            f"Generación exitosa: {from_cache} del cache + "
            f"{from_gen} generadas por IA"
        )
