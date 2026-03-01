"""
Main Protocol Analyzer Orchestrator
=====================================
Reads .anbx protocol files → sends to configured LLM providers 
→ parses structured JSON responses → exports CSV/JSON for evaluation.

Usage:
    python analyzer.py

Configure providers and protocol folder in config.py or via environment variables.
"""

import os
import glob
import time
from datetime import datetime
from typing import List

from prompts import build_prompt
from parser import parse_response
from exporter import export_results


# ── Import providers ──────────────────────────────────────────────────────────
# Comment out any provider you don't have an API key for
from llm_providers import (
    OpenAIProvider,
    AnthropicProvider,
    GeminiProvider,
    DeepSeekProvider,
)


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION  ── edit this section or use environment variables
# ══════════════════════════════════════════════════════════════════════════════

PROTOCOLS_FOLDER = "protocols"   # Folder containing .anbx files
RESULTS_FOLDER   = "results"     # Output folder
DELAY_BETWEEN_CALLS = 2          # Seconds between API calls (rate limiting)

# Add/remove providers here. Each entry: (ProviderClass, api_key, model)
def get_providers() -> list:
    providers = []

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        providers.append(OpenAIProvider(api_key=openai_key, model="gpt-4o"))

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        providers.append(AnthropicProvider(api_key=anthropic_key, model="claude-opus-4-6"))

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        providers.append(GeminiProvider(api_key=gemini_key, model="gemini-1.5-pro"))

    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if deepseek_key:
        providers.append(DeepSeekProvider(api_key=deepseek_key, model="deepseek-reasoner"))

    return providers

# ══════════════════════════════════════════════════════════════════════════════


def read_protocols(folder: str) -> List[dict]:
    """Load all .anbx (or .txt) protocol files from the specified folder."""
    patterns = [
        os.path.join(folder, "*.anbx"),
        os.path.join(folder, "*.txt"),
        os.path.join(folder, "*.anb"),
    ]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))

    protocols = []
    for filepath in sorted(files):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        protocols.append({
            "file": os.path.basename(filepath),
            "path": filepath,
            "content": content,
        })
        print(f"  📄 Loaded: {os.path.basename(filepath)}")

    return protocols


def analyze_protocol(provider, protocol: dict) -> dict:
    """Run one protocol through one LLM provider and return a result record."""
    system_prompt, user_prompt = build_prompt(protocol["content"])

    print(f"    → Sending to {provider.provider_name} ({provider.model})...", end=" ", flush=True)

    raw_response = provider.analyze(user_prompt, system_prompt)

    result = {
        "timestamp":       datetime.now().isoformat(),
        "protocol_file":   protocol["file"],
        "provider":        raw_response["provider"],
        "model":           raw_response["model"],
        "tokens_used":     raw_response["tokens_used"],
        "api_error":       raw_response["error"],
        "raw_llm_output":  raw_response["content"],
    }

    if raw_response["error"]:
        print(f"❌ API Error: {raw_response['error']}")
        result.update({"parsed_response": None, "parse_valid": False, "parse_issues": []})
        return result

    # Parse the structured JSON response
    parse_result = parse_response(raw_response["content"])
    result["parsed_response"] = parse_result["parsed"]
    result["parse_valid"]     = parse_result["valid"]
    result["parse_issues"]    = parse_result["issues"]

    status = "✅ Valid JSON" if parse_result["valid"] else f"⚠️  Parse issues: {parse_result['issues']}"
    print(status)

    # Print quick summary
    if parse_result["valid"] and parse_result["parsed"]:
        assessment = parse_result["parsed"].get("overall_assessment", {})
        vuln_count = len(parse_result["parsed"].get("vulnerabilities", []))
        print(f"       Rating: {assessment.get('security_rating','?')} | "
              f"Confidence: {assessment.get('confidence','?')} | "
              f"Vulnerabilities found: {vuln_count}")

    return result


def run():
    print("=" * 65)
    print("  Security Protocol Analyzer — LLM Comparative Study")
    print("=" * 65)

    # Load providers
    providers = get_providers()
    if not providers:
        print("\n❌ No providers configured. Set at least one API key:\n"
              "   OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, DEEPSEEK_API_KEY")
        return

    print(f"\n🔌 Active providers: {[f'{p.provider_name} ({p.model})' for p in providers]}")

    # Load protocols
    print(f"\n📂 Loading protocols from '{PROTOCOLS_FOLDER}/'...")
    protocols = read_protocols(PROTOCOLS_FOLDER)
    if not protocols:
        print(f"❌ No .anbx/.anb/.txt files found in '{PROTOCOLS_FOLDER}/'")
        return
    print(f"   Found {len(protocols)} protocol(s).\n")

    # Run analysis
    all_results = []
    total = len(protocols) * len(providers)
    current = 0

    for protocol in protocols:
        print(f"\n{'─' * 55}")
        print(f"  Protocol: {protocol['file']}")
        print(f"{'─' * 55}")

        for provider in providers:
            current += 1
            print(f"  [{current}/{total}] Provider: {provider.provider_name}")

            result = analyze_protocol(provider, protocol)
            all_results.append(result)

            if current < total:
                time.sleep(DELAY_BETWEEN_CALLS)

    # Export
    print(f"\n{'=' * 55}")
    print(f"  Analysis complete. {len(all_results)} total runs.")
    export_results(all_results, RESULTS_FOLDER)


if __name__ == "__main__":
    run()
