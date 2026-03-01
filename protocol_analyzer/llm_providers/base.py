"""
Base class for all LLM providers.
All providers must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.provider_name = self.__class__.__name__

    @abstractmethod
    def analyze(self, prompt: str, system_prompt: str) -> dict:
        """
        Send a prompt to the LLM and return the raw response dict.

        Returns:
            {
                "content": str,       # Raw text response from LLM
                "model": str,         # Model used
                "provider": str,      # Provider name
                "tokens_used": int,   # Total tokens consumed (if available)
                "error": str | None   # Error message if request failed
            }
        """
        pass

    def _error_response(self, error_msg: str) -> dict:
        return {
            "content": None,
            "model": self.model,
            "provider": self.provider_name,
            "tokens_used": 0,
            "error": str(error_msg),
        }
