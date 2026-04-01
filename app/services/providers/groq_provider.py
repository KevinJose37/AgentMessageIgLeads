import logging
import httpx
from .base import AIProvider

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(AIProvider):
    """
    Generic provider for any OpenAI-compatible API.
    Works with: Groq, OpenAI, DeepSeek, Together, and any other
    provider that implements the OpenAI chat completions format.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        provider_name: str = "openai",
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._provider_name = provider_name
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
        self._last_usage: dict = {}

    # ---- generation ----

    async def generate(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.7
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": 4096,
            "top_p": 0.9,
        }

        logger.info(
            "%s request: model=%s, temperature=%.2f",
            self._provider_name,
            self.model,
            temperature,
        )

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            self._last_usage = data.get("usage", {})
            logger.info(
                "%s response: %d tokens (prompt=%d, completion=%d)",
                self._provider_name,
                self._last_usage.get("total_tokens", 0),
                self._last_usage.get("prompt_tokens", 0),
                self._last_usage.get("completion_tokens", 0),
            )

            return content

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            body = e.response.text

            if status == 429:
                logger.warning("%s rate limit hit: %s", self._provider_name, body)
                raise ConnectionError(
                    f"{self._provider_name} rate limit exceeded: {body}"
                )
            elif status == 401:
                raise ConnectionError(f"{self._provider_name} API key inválida")
            else:
                logger.error("%s HTTP %d: %s", self._provider_name, status, body)
                raise ConnectionError(
                    f"{self._provider_name} error {status}: {body}"
                )

        except httpx.TimeoutException:
            raise TimeoutError(
                f"{self._provider_name} request timed out after {self.timeout}s"
            )

        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to {self._provider_name} API. Check internet."
            )

    # ---- health checks ----

    async def is_healthy(self) -> bool:
        try:
            response = await self.client.get("/models", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def is_model_loaded(self) -> bool:
        try:
            response = await self.client.get("/models", timeout=5.0)
            if response.status_code == 200:
                models = response.json().get("data", [])
                return any(self.model == m.get("id", "") for m in models)
            return False
        except Exception:
            return False

    # ---- lifecycle ----

    async def close(self):
        await self.client.aclose()

    @property
    def name(self) -> str:
        return f"{self._provider_name}/{self.model}"

    @property
    def last_usage(self) -> dict:
        return self._last_usage
