import logging
import httpx
from .base import AIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """
    Provider for Google Gemini API.
    Uses the Gemini REST API directly (not OpenAI-compatible format).

    Free tier: 15 RPM, 1,500 RPD, 1M tokens/min.
    Get key at: https://aistudio.google.com/apikey
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
        )

    # ---- generation ----

    async def generate(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.7
    ) -> str:
        url = (
            f"{self.BASE_URL}/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )

        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 4096,
                "topP": 0.9,
            },
        }

        logger.info("Gemini request: model=%s, temperature=%.2f", self.model, temperature)

        try:
            response = await self.client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            data = response.json()
            content = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )

            usage = data.get("usageMetadata", {})
            logger.info(
                "Gemini response: prompt=%d, completion=%d tokens",
                usage.get("promptTokenCount", 0),
                usage.get("candidatesTokenCount", 0),
            )

            return content

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            body = e.response.text

            if status == 429:
                logger.warning("Gemini rate limit: %s", body)
                raise ConnectionError(f"Gemini rate limit exceeded: {body}")
            elif status in (401, 403):
                raise ConnectionError("Gemini API key inválida o sin permisos")
            else:
                logger.error("Gemini HTTP %d: %s", status, body)
                raise ConnectionError(f"Gemini error {status}: {body}")

        except httpx.TimeoutException:
            raise TimeoutError(
                f"Gemini request timed out after {self.timeout}s"
            )

        except httpx.ConnectError:
            raise ConnectionError("Cannot connect to Gemini API. Check internet.")

    # ---- health checks ----

    async def is_healthy(self) -> bool:
        try:
            url = f"{self.BASE_URL}/models?key={self.api_key}"
            response = await self.client.get(url, timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def is_model_loaded(self) -> bool:
        try:
            url = f"{self.BASE_URL}/models/{self.model}?key={self.api_key}"
            response = await self.client.get(url, timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    # ---- lifecycle ----

    async def close(self):
        await self.client.aclose()

    @property
    def name(self) -> str:
        return f"gemini/{self.model}"
