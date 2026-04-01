from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Abstract base class for AI inference providers."""

    @abstractmethod
    async def generate(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.8
    ) -> str:
        """
        Send a prompt to the model and return the raw text response.

        Args:
            system_prompt: System-level instructions.
            user_prompt: The user's request.
            temperature: Sampling temperature (0.0–1.0).

        Returns:
            Raw text response from the model.
        """
        ...

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if the provider is reachable."""
        ...

    @abstractmethod
    async def is_model_loaded(self) -> bool:
        """Check if the target model is loaded and ready."""
        ...

    @abstractmethod
    async def close(self):
        """Clean up resources (HTTP clients, etc.)."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name, e.g. 'ollama/mistral'."""
        ...
