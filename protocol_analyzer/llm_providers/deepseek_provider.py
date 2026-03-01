"""
DeepSeek LLM Provider (uses OpenAI-compatible API)
Install: pip install openai
"""

from .base import BaseLLMProvider


class DeepSeekProvider(BaseLLMProvider):

    def __init__(self, api_key: str, model: str = "deepseek-reasoner"):
        super().__init__(api_key, model)
        try:
            from openai import OpenAI
            # DeepSeek uses an OpenAI-compatible endpoint
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )
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
                temperature=0,
            )
            return {
                "content": response.choices[0].message.content,
                "model": self.model,
                "provider": "DeepSeek",
                "tokens_used": response.usage.total_tokens,
                "error": None,
            }
        except Exception as e:
            return self._error_response(e)
