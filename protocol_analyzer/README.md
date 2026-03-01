# Security Protocol Analyzer — LLM Comparative Study
**MSc Cyber Security Dissertation Tool | Teesside University**

Automates sending security protocols (AnBx notation) to multiple LLM APIs and 
collecting structured JSON responses for comparative evaluation against formal 
verification tools (OFMC, ProVerif).

---

## Project Structure

```
protocol_analyzer/
├── analyzer.py              ← Main entry point (run this)
├── prompts.py               ← System prompt + analysis prompt template
├── parser.py                ← Validates and parses LLM JSON responses
├── exporter.py              ← Exports results to CSV and JSON
├── requirements.txt
├── .env.example             ← Copy to .env and add your API keys
│
├── llm_providers/
│   ├── base.py              ← Abstract base class (add new providers here)
│   ├── openai_provider.py   ← GPT-4o, GPT-3.5, etc.
│   ├── anthropic_provider.py← Claude models
│   ├── gemini_provider.py   ← Gemini models
│   └── deepseek_provider.py ← DeepSeek models
│
├── protocols/               ← Drop your .anbx protocol files here
│   ├── nsl.anbx
│   └── diffie_hellman.anbx
│
└── results/                 ← Auto-created on first run
    ├── full_results_<ts>.json
    └── summary_<ts>.csv
```

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Edit .env and add your keys

# 3. Add protocol files to the protocols/ folder
#    Supported formats: .anbx  .anb  .txt

# 4. Run
python analyzer.py
```

---

## Adding a New LLM Provider

1. Create `llm_providers/myprovider.py` inheriting from `BaseLLMProvider`
2. Implement the `analyze(prompt, system_prompt) -> dict` method
3. Add it to `llm_providers/__init__.py`
4. Add it to `get_providers()` in `analyzer.py`

```python
# llm_providers/myprovider.py
from .base import BaseLLMProvider

class MyProvider(BaseLLMProvider):
    def __init__(self, api_key, model="my-model"):
        super().__init__(api_key, model)
        # init your SDK client here

    def analyze(self, prompt, system_prompt):
        try:
            # call your API...
            return {
                "content": "...",       # raw LLM text
                "model": self.model,
                "provider": "MyProvider",
                "tokens_used": 0,
                "error": None,
            }
        except Exception as e:
            return self._error_response(e)
```

---

## Output Format

### CSV (summary_<timestamp>.csv)
One row per (protocol × provider) run. Key columns:
- `protocol_file`, `provider`, `model`, `tokens_used`
- `security_rating`, `confidence`, `vulnerability_count`
- `confidentiality_supported`, `authentication_supported`, ... (per property)
- `vulnerabilities_summary`

### JSON (full_results_<timestamp>.json)
Complete structured data including attack traces, mitigation recommendations,
formal verification hints, and raw LLM output for audit.

---

## Bias Prevention
The `build_prompt()` function in `prompts.py` strips the `Protocol:` name line 
before sending to the LLM, preventing the model from recalling memorised analyses 
of well-known protocols by name.
