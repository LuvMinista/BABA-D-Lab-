"""
OpenAI LLM Provider (GPT-4, GPT-3.5, etc.)
Install: pip install openai
"""

from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        super().__init__(api_key, model)
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("Run: pip install openai")

    def analyze(self, prompt: str, system_prompt: str) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,  # deterministic for research consistency
            )
            return {
                "content": response.choices[0].message.content,
                "model": self.model,
                "provider": "OpenAI",
                "tokens_used": response.usage.total_tokens,
                "error": None,
            }
        except Exception as e:
            return self._error_response(e)
