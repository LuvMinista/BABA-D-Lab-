"""
Parses and validates the structured JSON response from LLM providers.

Expected LLM response schema
-----------------------------
{
  "goals": [
    {
      "attack":       "ATTACK" | "NO_ATTACK" | "unknown",
      "number_goals": 1 or 1,
      "goal":         "<goal description>"
    },
    ...
  ]
}

Falls back gracefully when the LLM returns malformed JSON.
"""

import json
import re
from typing import Optional


VALID_ATTACK_VALUES = {"ATTACK", "NO_ATTACK", "UNKNOWN"}   # checked case-insensitively


def parse_response(raw_content: str) -> dict:
    """
    Attempt to parse the LLM's raw text output into a validated dict.

    Returns a dict with:
        "parsed"  : dict | None   – the parsed + normalised JSON, or None on failure
        "valid"   : bool          – True only when schema is fully correct
        "issues"  : list[str]     – any parse or schema warnings
        "raw"     : str           – original LLM text for audit
    """
    issues = []

    if not raw_content:
        return {"parsed": None, "valid": False,
                "issues": ["Empty response from LLM"], "raw": ""}

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

    # 4. Top-level schema: must have "goals" key
    if "goals" not in parsed:
        issues.append('Missing required top-level key: "goals".')
        return {"parsed": parsed, "valid": False, "issues": issues, "raw": raw_content}

    if not isinstance(parsed["goals"], list):
        issues.append('"goals" must be a JSON array.')
        return {"parsed": parsed, "valid": False, "issues": issues, "raw": raw_content}

    # 5. Per-entry validation + normalisation
    entry_issues = []
    for idx, entry in enumerate(parsed["goals"]):
        tag = f"goals[{idx}]"

        if not isinstance(entry, dict):
            entry_issues.append(f"{tag}: entry is not an object.")
            continue

        # ── attack ────────────────────────────────────────────────────────────
        if "attack" not in entry:
            entry_issues.append(f'{tag}: missing "attack" field.')
        else:
            val = str(entry["attack"]).strip().upper()
            if val not in VALID_ATTACK_VALUES:
                entry_issues.append(
                    f'{tag}: "attack" value "{entry["attack"]}" is not one of '
                    f'ATTACK | NO_ATTACK | unknown.'
                )
            else:
                # Normalise to uppercase for consistent downstream handling
                entry["attack"] = val

        # ── number_goals ──────────────────────────────────────────────────────
        if "number_goals" not in entry:
            entry_issues.append(f'{tag}: missing "number_goals" field.')
        else:
            try:
                entry["number_goals"] = int(entry["number_goals"])
            except (TypeError, ValueError):
                entry_issues.append(
                    f'{tag}: "number_goals" is not an integer: {entry["number_goals"]!r}.'
                )

        # ── goal ─────────────────────────────────────────────────────────────
        if "goal" not in entry:
            entry_issues.append(f'{tag}: missing "goal" field.')
        else:
            entry["goal"] = str(entry["goal"]).strip()

    issues.extend(entry_issues)

    if entry_issues:
        return {"parsed": parsed, "valid": False, "issues": issues, "raw": raw_content}

    return {"parsed": parsed, "valid": True, "issues": issues, "raw": raw_content}


# ── Internal helpers ──────────────────────────────────────────────────────────

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
