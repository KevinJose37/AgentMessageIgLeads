import json
import logging
import re
import time
from typing import Optional, Callable

from ..config import Settings
from ..models.enums import GenerationStatus
from .cache_service import CacheService
from .providers.base import AIProvider
from .providers.groq_provider import OpenAICompatibleProvider
from .providers.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)


def build_provider_chain(settings: Settings) -> list[AIProvider]:
    """
    Build ordered list of AI providers. First available wins.
    Add an API key in .env to activate any provider.

    Chain order: Groq → Gemini → OpenAI
    """
    providers: list[AIProvider] = []

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

    if settings.GEMINI_API_KEY:
        providers.append(
            GeminiProvider(
                api_key=settings.GEMINI_API_KEY,
                model=settings.GEMINI_MODEL,
                timeout=settings.GEMINI_TIMEOUT,
            )
        )
        logger.info("Provider registered: gemini/%s", settings.GEMINI_MODEL)

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
    else:
        logger.error(
            "No AI providers configured! Set at least one API key in .env "
            "(GROQ_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY)"
        )

    return providers


class BaseAIService:
    """
    Shared infrastructure for all AI-powered services.
    Handles: provider chain, fallback, batch generation, caching, JSON parsing.
    """

    def __init__(
        self,
        providers: list[AIProvider],
        cache: Optional[CacheService],
        settings: Settings,
    ):
        self.providers = providers
        self.cache = cache
        self.settings = settings
        self._last_error: str = ""
        self._active_provider_name: str = ""

    # ------------------------------------------------------------------
    # Core generation with provider fallback
    # ------------------------------------------------------------------

    async def _generate_with_providers(
        self,
        build_prompt_fn: Callable[[int], tuple[str, str]],
        count: int,
        cache_key: Optional[str] = None,
        cache_tone: Optional[str] = None,
    ) -> dict:
        """
        Generate text using the provider chain with fallback.

        Args:
            build_prompt_fn: Function(batch_size) -> (system_prompt, user_prompt)
            count: Total number of items to generate.
            cache_key: Optional message key for cache lookup.
            cache_tone: Optional tone for cache lookup.

        Returns:
            Dict with: items, from_cache, from_generation, provider, elapsed, error
        """
        start = time.time()
        self._last_error = ""
        from_cache = 0
        from_generation = 0
        all_items: list[str] = []

        # 1️⃣ Try cache
        if self.cache and cache_key and cache_tone:
            cached = self.cache.get_cached_variations(
                message=cache_key,
                tone=cache_tone,
                num_requested=count,
            )
            if cached:
                all_items.extend(cached)
                from_cache = len(cached)
                logger.info("Cache provided %d items", from_cache)

        # 2️⃣ Generate remaining
        remaining = count - len(all_items)

        if remaining > 0:
            generated = await self._batch_generate(build_prompt_fn, remaining)
            all_items.extend(generated)
            from_generation = len(generated)

            # Store in cache
            if self.cache and generated and cache_key and cache_tone:
                self.cache.store_variations(
                    message=cache_key,
                    tone=cache_tone,
                    variations=generated,
                )

        # 3️⃣ Trim
        all_items = all_items[:count]
        elapsed = time.time() - start

        # Status
        if len(all_items) == 0:
            status = GenerationStatus.ERROR
        elif len(all_items) < count:
            status = GenerationStatus.PARTIAL
        elif from_cache > 0 and from_generation == 0:
            status = GenerationStatus.CACHED
        else:
            status = GenerationStatus.SUCCESS

        return {
            "status": status,
            "items": all_items,
            "total": len(all_items),
            "from_cache": from_cache,
            "from_generation": from_generation,
            "provider": self._active_provider_name,
            "generation_time_seconds": round(elapsed, 2),
            "error": self._last_error,
        }

    # ------------------------------------------------------------------
    # Batch generation with provider fallback
    # ------------------------------------------------------------------

    async def _batch_generate(
        self,
        build_prompt_fn: Callable[[int], tuple[str, str]],
        count: int,
    ) -> list[str]:
        """Generate items in batches, trying each provider in order."""
        if not self.providers:
            self._last_error = (
                "No hay providers de IA configurados. "
                "Configura al menos una API key en .env"
            )
            return []

        all_generated: list[str] = []
        batch_size = self.settings.BATCH_SIZE
        empty_retries = 0
        max_empty_retries = 2

        for provider in self.providers:
            try:
                is_healthy = await provider.is_healthy()
                if not is_healthy:
                    logger.warning(
                        "Provider %s not healthy, trying next", provider.name
                    )
                    continue

                self._active_provider_name = provider.name
                logger.info("Using provider: %s", provider.name)

                while len(all_generated) < count:
                    current_batch = min(batch_size, count - len(all_generated))

                    system_prompt, user_prompt = build_prompt_fn(current_batch)

                    raw_response = await provider.generate(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=self.settings.TEMPERATURE,
                    )

                    logger.info(
                        "Raw response (first 300 chars): %s",
                        raw_response[:300],
                    )

                    items = self._parse_json_array(raw_response)

                    if not items:
                        empty_retries += 1
                        logger.warning(
                            "Parse returned 0 items (attempt %d/%d). Raw: %s",
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

                    all_generated.extend(items)
                    empty_retries = 0

                    logger.info(
                        "Batch complete: requested=%d, parsed=%d, total=%d/%d",
                        current_batch,
                        len(items),
                        len(all_generated),
                        count,
                    )

                if all_generated:
                    break

            except (TimeoutError, ConnectionError) as e:
                logger.warning(
                    "Provider %s failed: %s — trying next", provider.name, e,
                )
                self._last_error = f"{provider.name}: {e}"
                continue
            except Exception as e:
                logger.exception(
                    "Unexpected error with %s: %s", provider.name, e,
                )
                self._last_error = f"{provider.name}: {type(e).__name__}: {e}"
                continue

        return all_generated

    # ------------------------------------------------------------------
    # JSON array parsing (shared by all services)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json_array(raw: str) -> list[str]:
        """
        Parse raw model response into a list of strings.
        Handles: JSON arrays, objects wrapping arrays, numbered lists.
        """
        cleaned = raw.strip()

        # Strip markdown code fences
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()

        # Strategy 1: direct JSON parse
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if v and str(v).strip()]
            if isinstance(parsed, dict):
                for key in (
                    "variations", "comments", "messages", "results",
                    "versiones", "comentarios", "data", "versions",
                    "responses",
                ):
                    if key in parsed and isinstance(parsed[key], list):
                        return [
                            str(v).strip()
                            for v in parsed[key]
                            if v and str(v).strip()
                        ]
        except json.JSONDecodeError:
            pass

        # Strategy 2: extract JSON array from text
        try:
            match = re.search(r"\[[\s\S]*\]", raw)
            if match:
                parsed = json.loads(match.group())
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if v and str(v).strip()]
        except json.JSONDecodeError:
            pass

        # Strategy 3: numbered list fallback
        lines = raw.strip().split("\n")
        result: list[str] = []
        for line in lines:
            line_clean = re.sub(r"^[\d]+[.\)\-]\s*", "", line.strip())
            line_clean = line_clean.strip("\"'")
            if line_clean and len(line_clean) > 5:
                result.append(line_clean)

        if result:
            logger.warning(
                "JSON parse failed — fell back to list extraction (%d items)",
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
    # Status messages
    # ------------------------------------------------------------------

    @staticmethod
    def _status_message(
        status: GenerationStatus,
        from_cache: int,
        from_gen: int,
        error: str = "",
        item_name: str = "items",
    ) -> str:
        if status == GenerationStatus.CACHED:
            return (
                f"Todos los {from_cache} {item_name} servidos "
                f"desde cache (con transformaciones)"
            )
        if status == GenerationStatus.PARTIAL:
            return (
                f"Generación parcial: {from_cache} del cache + "
                f"{from_gen} generados por IA"
            )
        if status == GenerationStatus.ERROR:
            base = f"No se pudieron generar {item_name}."
            if error:
                return f"{base} Detalle: {error}"
            return f"{base} Verifica la configuración del provider."
        return (
            f"Generación exitosa: {from_cache} del cache + "
            f"{from_gen} generados por IA"
        )
