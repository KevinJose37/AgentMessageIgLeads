import logging
import httpx
from .base import AIProvider

logger = logging.getLogger(__name__)


class OllamaProvider(AIProvider):
    """
    AI provider that talks to a local Ollama instance via its REST API.
    Optimized for Mistral 7B Instruct on CPU.
    """

    def __init__(self, base_url: str, model: str, timeout: int = 600):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0)
        )

        # Stats from last generation (for response metadata)
        self._last_eval_count: int = 0
        self._last_duration_s: float = 0.0

    # ---- generation ----

    async def generate(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.8
    ) -> str:
        """
        Call Ollama /api/chat for instruct-style generation.
        Uses streaming=false to get the full response at once.
        """
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 4096,
                # Keep context window reasonable for 8GB RAM
                "num_ctx": 4096,
            },
        }

        logger.info(
            "Ollama request: model=%s, temperature=%.2f", self.model, temperature
        )

        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            content = data.get("message", {}).get("content", "")

            # Store stats
            self._last_eval_count = data.get("eval_count", 0)
            total_ns = data.get("total_duration", 0)
            self._last_duration_s = total_ns / 1e9 if total_ns else 0.0

            logger.info(
                "Ollama response: %d tokens in %.1fs",
                self._last_eval_count,
                self._last_duration_s,
            )

            return content

        except httpx.TimeoutException:
            logger.error("Ollama request timed out after %ds", self.timeout)
            raise TimeoutError(
                f"Ollama request timed out after {self.timeout}s. "
                f"CPU inference for Mistral 7B can be slow — "
                f"try reducing num_variations."
            )
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama at %s", self.base_url)
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Make sure Ollama is running: ollama serve"
            )
        except httpx.HTTPStatusError as e:
            logger.error("Ollama HTTP error: %s", e.response.text)
            raise ConnectionError(f"Ollama error: {e.response.text}")

    # ---- health checks ----

    async def is_healthy(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/tags",
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    async def is_model_loaded(self) -> bool:
        """Check if the target model is available in Ollama."""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/tags",
                timeout=5.0,
            )
            if response.status_code == 200:
                models = response.json().get("models", [])
                return any(self.model in m.get("name", "") for m in models)
            return False
        except Exception:
            return False

    # ---- lifecycle ----

    async def close(self):
        await self.client.aclose()

    @property
    def name(self) -> str:
        return f"ollama/{self.model}"

    @property
    def last_eval_count(self) -> int:
        return self._last_eval_count

    @property
    def last_duration_seconds(self) -> float:
        return self._last_duration_s
