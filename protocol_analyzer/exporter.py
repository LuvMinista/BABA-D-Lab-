"""
Exports analysis results to CSV and JSON for evaluation and comparison.

CSV layout  (one row per LLM-predicted goal)
--------------------------------------------
Each row represents a single security goal as predicted by the LLM for one
(protocol × provider) run.  The same protocol's OFMC ground-truth rows are
stored as a compact summary string so every row is self-contained.

Core columns
  protocol_name        human-readable name extracted from the file
  protocol_file        filename
  provider / model     which LLM produced this prediction
  full_protocol        complete unmodified protocol text (for audit)

Per-goal LLM prediction columns  (the primary research data)
  llm_goal_index       0-based index within this run's goals list
  llm_attack           ATTACK | NO_ATTACK | unknown
  llm_number_goals     always 1 per entry (matches OFMC row convention)
  llm_goal             the security goal text the LLM evaluated

OFMC ground-truth columns  (for direct accuracy comparison)
  ofmc_attack          ATTACK | NO_ATTACK | unknown  (from the file)
  ofmc_number_goals    number_goals value from the file
  ofmc_goal            goal text from the file
  ofmc_all_verdicts    compact summary of ALL OFMC rows for this protocol,
                       e.g.  "NO_ATTACK:B auth A | ATTACK:B *->* A: NB2"

JSON output
-----------
Full fidelity — every result dict including full_protocol text, the complete
ofmc_results list, and the full parsed LLM response is written as-is.
"""

import csv
import json
import os
from datetime import datetime
from typing import List


def export_results(results: List[dict], output_dir: str = "results") -> dict:
    """
    Export all results to:
      results/full_results_<timestamp>.json   – complete raw data
      results/summary_<timestamp>.csv         – one row per LLM-predicted goal

    Args:
        results:    List of result dicts produced by the analyzer.
        output_dir: Directory to write output files.

    Returns:
        {"json_path": str, "csv_path": str}
    """
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = os.path.join(output_dir, f"full_results_{ts}.json")
    csv_path  = os.path.join(output_dir, f"summary_{ts}.csv")

    # ── Full JSON dump ────────────────────────────────────────────────────────
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # ── Flat CSV: one row per LLM-predicted goal ──────────────────────────────
    csv_rows = []
    for r in results:
        base       = _build_base_columns(r)
        llm_goals  = _extract_llm_goals(r)
        ofmc_rows  = r.get("ofmc_results", [])

        # Compact OFMC summary string for the whole protocol
        ofmc_summary = " | ".join(
            f"{o['attack']}:{o['goal']}" for o in ofmc_rows
        )

        if llm_goals:
            for idx, goal_entry in enumerate(llm_goals):
                # Pair with the OFMC row at the same index (best-effort)
                ofmc_match = ofmc_rows[idx] if idx < len(ofmc_rows) else {}

                row = dict(base)
                # ── LLM prediction ────────────────────────────────────────────
                row["llm_goal_index"]   = idx
                row["llm_attack"]       = goal_entry.get("attack", "")
                row["llm_number_goals"] = goal_entry.get("number_goals", "")
                row["llm_goal"]         = goal_entry.get("goal", "")
                row["llm_reasoning"]    = goal_entry.get("reasoning", "")
                # ── OFMC ground truth (paired by index) ───────────────────────
                row["ofmc_attack"]       = ofmc_match.get("attack", "")
                row["ofmc_number_goals"] = ofmc_match.get("number_goals", "")
                row["ofmc_goal"]         = ofmc_match.get("goal", "")
                row["ofmc_all_verdicts"] = ofmc_summary
                csv_rows.append(row)
        else:
            # No LLM goals parsed — still write one row so the run is visible
            row = dict(base)
            row["llm_goal_index"]    = ""
            row["llm_attack"]        = ""
            row["llm_number_goals"]  = ""
            row["llm_goal"]          = ""
            row["llm_reasoning"]     = ""
            row["ofmc_attack"]       = ""
            row["ofmc_number_goals"] = ""
            row["ofmc_goal"]         = ""
            row["ofmc_all_verdicts"] = ofmc_summary
            csv_rows.append(row)

    if csv_rows:
        fieldnames = list(csv_rows[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

    print(f"\n✅ Results saved:")
    print(f"   JSON → {json_path}")
    print(f"   CSV  → {csv_path}")
    return {"json_path": json_path, "csv_path": csv_path}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_base_columns(r: dict) -> dict:
    """Columns that are the same for every goal row within one result."""
    return {
        # ── Identification ────────────────────────────────────────────────────
        "timestamp":        r.get("timestamp", ""),
        "start_time":       r.get("start_time", ""),
        "end_time":         r.get("end_time", ""),
        "duration_seconds": r.get("duration_seconds", ""),
        "protocol_file":    r.get("protocol_file", ""),
        "protocol_name":    r.get("protocol_name", ""),
        "provider":         r.get("provider", ""),
        "model":            r.get("model", ""),
        "tokens_used":      r.get("tokens_used", 0),
        # ── Full protocol source (unmodified) ─────────────────────────────────
        "full_protocol":    r.get("full_protocol", ""),
        # ── Parse health ──────────────────────────────────────────────────────
        "parse_valid":      r.get("parse_valid", False),
        "parse_issues":     "; ".join(r.get("parse_issues", [])),
        "api_error":        r.get("api_error", "") or "",
        # ── Total goal counts (summary) ───────────────────────────────────────
        "llm_total_goals":  len(_extract_llm_goals(r)),
        "ofmc_total_goals": len(r.get("ofmc_results", [])),
    }


def _extract_llm_goals(r: dict) -> list:
    """Safely return the goals list from a parsed LLM response."""
    parsed = r.get("parsed_response") or {}
    return parsed.get("goals", []) if isinstance(parsed, dict) else []
