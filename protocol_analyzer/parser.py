"""
Parses and validates the structured JSON response from LLM providers.
Falls back gracefully when the LLM returns malformed JSON.
"""

import json
import re
from typing import Optional


REQUIRED_TOP_LEVEL_KEYS = {
    "protocol_summary",
    "security_properties",
    "vulnerabilities",
    "formal_verification_hints",
    "overall_assessment",
}


def parse_response(raw_content: str) -> dict:
    """
    Attempt to parse the LLM's raw text output into a validated dict.

    Returns a dict with:
        - "parsed"  : dict | None   (the parsed JSON, or None on failure)
        - "valid"   : bool          (True if all required keys present)
        - "issues"  : list[str]     (any parse or schema warnings)
        - "raw"     : str           (original LLM text for audit)
    """
    issues = []

    if not raw_content:
        return {"parsed": None, "valid": False, "issues": ["Empty response from LLM"], "raw": ""}

    # 1. Try direct parse
    parsed = _try_json_parse(raw_content)

    # 2. Try extracting JSON block from markdown fences
    if parsed is None:
        json_block = _extract_json_block(raw_content)
        if json_block:
            parsed = _try_json_parse(json_block)
            if parsed:
                issues.append("JSON was wrapped in markdown fences — extracted successfully.")

    # 3. Still failed
    if parsed is None:
        issues.append("Could not parse JSON from LLM response.")
        return {"parsed": None, "valid": False, "issues": issues, "raw": raw_content}

    # 4. Schema validation
    missing = REQUIRED_TOP_LEVEL_KEYS - set(parsed.keys())
    if missing:
        issues.append(f"Missing required keys: {missing}")
        return {"parsed": parsed, "valid": False, "issues": issues, "raw": raw_content}

    return {"parsed": parsed, "valid": True, "issues": issues, "raw": raw_content}


def _try_json_parse(text: str) -> Optional[dict]:
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_json_block(text: str) -> Optional[str]:
    """Extract JSON content from ```json ... ``` or ``` ... ``` blocks."""
    pattern = r"```(?:json)?\s*(\{[\s\S]*?\})\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1)
    # Fallback: find the first { ... } spanning multiple lines
    match = re.search(r"(\{[\s\S]+\})", text)
    return match.group(1) if match else None
