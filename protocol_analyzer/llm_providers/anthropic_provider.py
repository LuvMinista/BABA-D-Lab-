"""
Anthropic Claude LLM Provider
Install: pip install anthropic
"""

from .base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):

    def __init__(self, api_key: str, model: str = "claude-opus-4-6"):
        super().__init__(api_key, model)
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("Run: pip install anthropic")

    def analyze(self, prompt: str, system_prompt: str) -> dict:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            return {
                "content": response.content[0].text,
                "model": self.model,
                "provider": "Anthropic",
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
                "error": None,
            }
        except Exception as e:
            return self._error_response(e)
