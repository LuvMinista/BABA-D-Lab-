"""
Google Gemini LLM Provider
Install: pip install google-generativeai
"""

from .base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        super().__init__(api_key, model)
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.genai = genai
            self.client = genai.GenerativeModel(model)
        except ImportError:
            raise ImportError("Run: pip install google-generativeai")

    def analyze(self, prompt: str, system_prompt: str) -> dict:
        try:
            full_prompt = f"{system_prompt}\n\n{prompt}"
            response = self.client.generate_content(
                full_prompt,
                generation_config=self.genai.GenerationConfig(temperature=0),
            )
            # Estimate tokens (Gemini returns usage metadata)
            tokens = 0
            if hasattr(response, "usage_metadata"):
                tokens = (
                    response.usage_metadata.prompt_token_count
                    + response.usage_metadata.candidates_token_count
                )
            return {
                "content": response.text,
                "model": self.model,
                "provider": "Google Gemini",
                "tokens_used": tokens,
                "error": None,
            }
        except Exception as e:
            return self._error_response(e)
