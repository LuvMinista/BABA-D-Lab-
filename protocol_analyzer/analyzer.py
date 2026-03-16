"""
Main Protocol Analyzer Orchestrator
=====================================
Reads .anbx protocol files → sends to configured LLM providers
→ parses structured JSON responses → exports CSV/JSON for evaluation.

Usage:
    python analyzer.py

Configure providers and protocol folder via environment variables or the
CONFIGURATION section below.

Batch mode:
    Providers that expose `supports_batch = True` (currently AnthropicProvider)
    submit all their protocol requests as a single Message Batch, which is
    ~50 % cheaper and avoids per-request rate-limit pressure.
    All other providers run sequentially.

What is stored per result
--------------------------
  protocol_name        – extracted from the "Protocol:" line in the file
  full_protocol        – complete, unmodified file content
  ofmc_results         – list of OFMC verdict rows (attack / number_goals / goal)
  … plus the usual LLM analysis fields
"""

import os
import glob
import time
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv

from prompts import build_prompt, extract_protocol_name, extract_ofmc_results
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

PROTOCOLS_FOLDER    = "protocols"   # Folder containing .anbx files
RESULTS_FOLDER      = "results"     # Output folder
DELAY_BETWEEN_CALLS = 2             # Seconds between sequential API calls

load_dotenv()


def get_providers() -> list:
    """Build the active provider list from environment API keys."""
    providers = []

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        providers.append(OpenAIProvider(api_key=openai_key, model="gpt-4o"))

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        providers.append(AnthropicProvider(api_key=anthropic_key, model="claude-opus-4-6"))

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        providers.append(GeminiProvider(api_key=gemini_key, model="gemini-2.0-flash"))

    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if deepseek_key:
        providers.append(DeepSeekProvider(api_key=deepseek_key, model="deepseek-reasoner"))

    return providers

# ══════════════════════════════════════════════════════════════════════════════


# ── User input helpers ────────────────────────────────────────────────────────

def ask_protocol_count(total_available: int) -> int:
    """
    Interactively ask the user how many protocols to analyse.
    Accepts a positive integer or blank/0/'all' to analyse all.
    Keeps prompting until valid input is received.
    """
    print(f"\n  {total_available} protocol(s) found in '{PROTOCOLS_FOLDER}/'.")
    while True:
        raw = input(
            f"  How many protocols to analyse? "
            f"[1–{total_available}, or press Enter for all]: "
        ).strip()

        if raw == "" or raw.lower() == "all":
            return total_available

        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= total_available:
                return n
            print(f"  ⚠️  Please enter a number between 1 and {total_available}.")
        else:
            print("  ⚠️  Invalid input. Enter a number or press Enter for all.")


# ── Protocol loading ──────────────────────────────────────────────────────────

def read_protocols(folder: str) -> List[dict]:
    """
    Load all .anbx / .anb / .txt protocol files from the specified folder.

    Each protocol dict contains:
        file            – filename only (e.g. "nsl.anbx")
        path            – full filesystem path
        content         – complete, unmodified file text
        protocol_name   – value of the "Protocol:" line (or the filename stem)
        ofmc_results    – list of OFMC verdict rows parsed from the file
    """
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

        # Extract metadata – these are stored but NOT passed to the LLM
        name = extract_protocol_name(content)
        if not name:
            # Fall back to the filename stem (e.g. "nsl" from "nsl.anbx")
            name = os.path.splitext(os.path.basename(filepath))[0]

        ofmc_results = extract_ofmc_results(content)

        protocols.append({
            "file":          os.path.basename(filepath),
            "path":          filepath,
            "content":       content,          # full, unmodified
            "protocol_name": name,
            "ofmc_results":  ofmc_results,
        })

        ofmc_summary = (
            f"{len(ofmc_results)} OFMC row(s)"
            if ofmc_results else "no OFMC rows detected"
        )
        print(f"  📄 Loaded: {os.path.basename(filepath)}"
              f"  [{name}]  ({ofmc_summary})")

    return protocols


# ── Single-call analysis (non-batch providers) ────────────────────────────────

def analyze_protocol(provider, protocol: dict) -> dict:
    """Run one protocol through one provider (sequential / non-batch)."""
    system_prompt, user_prompt, extracted_name = build_prompt(protocol["content"])
    # Prefer the name returned by build_prompt (extracted before stripping)
    # so the result dict is never missing the real protocol name.
    if extracted_name:
        protocol["protocol_name"] = extracted_name

    print(f"    → Sending to {provider.provider_name} ({provider.model})…",
          end=" ", flush=True)

    raw_response = provider.analyze(user_prompt, system_prompt)
    return _build_result(protocol, raw_response)


# ── Batch analysis (Anthropic and any future batch-capable provider) ──────────

def analyze_protocols_batch(provider, protocols: List[dict]) -> List[dict]:
    """
    Submit all protocols to a batch-capable provider in one API call.
    Returns a list of result dicts in the same order as `protocols`.
    """
    batch_requests = []
    for protocol in protocols:
        system_prompt, user_prompt, extracted_name = build_prompt(protocol["content"])
        # Prefer name returned before stripping over any previously stored value
        if extracted_name:
            protocol["protocol_name"] = extracted_name
        batch_requests.append({
            "custom_id":     protocol["file"],
            "user_prompt":   user_prompt,
            "system_prompt": system_prompt,
        })

    print(f"\n  ⚡ Using Batch API for {provider.provider_name} "
          f"({len(protocols)} protocol(s))…")

    raw_responses = provider.analyze_batch(batch_requests)

    response_map = {r["custom_id"]: r for r in raw_responses}

    results = []
    for protocol in protocols:
        raw = response_map.get(protocol["file"])
        if raw is None:
            raw = {
                "content": "", "model": provider.model,
                "provider": provider.provider_name,
                "tokens_used": 0,
                "error": "Missing from batch response",
            }
        result = _build_result(protocol, raw)
        _print_result_summary(protocol, result)
        results.append(result)

    return results


# ── Shared result builder ─────────────────────────────────────────────────────

def _build_result(protocol: dict, raw_response: dict) -> dict:
    """
    Assemble a standardised result record from a raw provider response.

    Fields added beyond the original:
        protocol_name        – human-readable name (NOT sent to LLM)
        full_protocol        – complete, unmodified protocol text
        ofmc_results         – list of OFMC verdict dicts
    """
    result = {
        "timestamp":          datetime.now().isoformat(),
        "protocol_file":      protocol["file"],
        "protocol_name":      protocol.get("protocol_name", ""),
        "full_protocol":      protocol.get("content", ""),
        "ofmc_results":       protocol.get("ofmc_results", []),
        "provider":           raw_response.get("provider", "Unknown"),
        "model":              raw_response.get("model", ""),
        "tokens_used":        raw_response.get("tokens_used", 0),
        "api_error":          raw_response.get("error"),
        "raw_llm_output":     raw_response.get("content", ""),
    }

    if raw_response.get("error"):
        result.update({"parsed_response": None, "parse_valid": False, "parse_issues": []})
        return result

    parse_result = parse_response(raw_response["content"])
    result["parsed_response"] = parse_result["parsed"]
    result["parse_valid"]     = parse_result["valid"]
    result["parse_issues"]    = parse_result["issues"]

    return result


def _print_result_summary(protocol: dict, result: dict) -> None:
    """Print a one-line summary for a completed result."""
    prefix = f"  {protocol['file']} ({protocol.get('protocol_name', '')}) →"
    if result.get("api_error"):
        print(f"{prefix} ❌ API Error: {result['api_error']}")
        return

    status = ("✅ Valid JSON" if result["parse_valid"]
              else f"⚠️  Parse issues: {result['parse_issues']}")
    print(f"{prefix} {status}", end="")

    if result["parse_valid"] and result.get("parsed_response"):
        assessment = result["parsed_response"].get("overall_assessment", {})
        vuln_count = len(result["parsed_response"].get("vulnerabilities", []))
        print(f"  |  Rating: {assessment.get('security_rating', '?')}  "
              f"Confidence: {assessment.get('confidence', '?')}  "
              f"Vulnerabilities: {vuln_count}", end="")

    # Print OFMC ground truth if available
    ofmc = result.get("ofmc_results", [])
    if ofmc:
        attacks = sum(1 for r in ofmc if r["attack"] == "ATTACK")
        print(f"  |  OFMC: {len(ofmc)} goal(s), {attacks} ATTACK(s)", end="")

    print()


# ── Main orchestrator ─────────────────────────────────────────────────────────

def run():
    print("=" * 65)
    print("  Security Protocol Analyzer — LLM Comparative Study")
    print("=" * 65)

    # ── Load providers ────────────────────────────────────────────────────────
    providers = get_providers()
    if not providers:
        print(
            "\n❌ No providers configured. Set at least one API key:\n"
            "   OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, DEEPSEEK_API_KEY"
        )
        return

    print(f"\n🔌 Active providers: "
          f"{[f'{p.provider_name} ({p.model})' for p in providers]}")

    # ── Load all protocols ────────────────────────────────────────────────────
    print(f"\n📂 Loading protocols from '{PROTOCOLS_FOLDER}/'…")
    all_protocols = read_protocols(PROTOCOLS_FOLDER)
    if not all_protocols:
        print(f"❌ No .anbx/.anb/.txt files found in '{PROTOCOLS_FOLDER}/'")
        return

    # ── Ask how many to analyse ───────────────────────────────────────────────
    count = ask_protocol_count(len(all_protocols))
    protocols = all_protocols[:count]
    print(f"\n  ✔  Analysing {len(protocols)} of {len(all_protocols)} protocol(s).\n")

    # ── Separate batch-capable from sequential providers ──────────────────────
    batch_providers      = [p for p in providers if getattr(p, "supports_batch", False)]
    sequential_providers = [p for p in providers if not getattr(p, "supports_batch", False)]

    all_results: List[dict] = []

    # ── Batch providers ───────────────────────────────────────────────────────
    for provider in batch_providers:
        print(f"\n{'─' * 55}")
        print(f"  Provider (Batch): {provider.provider_name} ({provider.model})")
        print(f"{'─' * 55}")
        batch_results = analyze_protocols_batch(provider, protocols)
        all_results.extend(batch_results)

    # ── Sequential providers ──────────────────────────────────────────────────
    total_seq = len(protocols) * len(sequential_providers)
    current   = 0

    for protocol in protocols:
        for provider in sequential_providers:
            current += 1
            print(f"\n{'─' * 55}")
            print(f"  [{current}/{total_seq}] Protocol: {protocol['file']}"
                  f"  ({protocol.get('protocol_name', '')})  |  "
                  f"Provider: {provider.provider_name}")
            print(f"{'─' * 55}")

            result = analyze_protocol(provider, protocol)
            _print_result_summary(protocol, result)
            all_results.append(result)

            if current < total_seq:
                time.sleep(DELAY_BETWEEN_CALLS)

    # ── Export ────────────────────────────────────────────────────────────────
    print(f"\n{'=' * 55}")
    print(f"  Analysis complete. {len(all_results)} total run(s).")
    export_results(all_results, RESULTS_FOLDER)


if __name__ == "__main__":
    run()
