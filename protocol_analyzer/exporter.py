"""
Exports analysis results to CSV and JSON for evaluation and comparison.
"""

import csv
import json
import os
from datetime import datetime
from typing import List


def export_results(results: List[dict], output_dir: str = "results") -> dict:
    """
    Export all results to:
      - results/full_results_<timestamp>.json   (complete raw data)
      - results/summary_<timestamp>.csv         (flat comparison table)

    Args:
        results: List of result dicts produced by the analyzer.
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

    # ── Flat CSV summary ──────────────────────────────────────────────────────
    csv_rows = []
    for r in results:
        base = {
            "timestamp":           r.get("timestamp", ""),
            "protocol_file":       r.get("protocol_file", ""),
            "provider":            r.get("provider", ""),
            "model":               r.get("model", ""),
            "tokens_used":         r.get("tokens_used", 0),
            "parse_valid":         r.get("parse_valid", False),
            "parse_issues":        "; ".join(r.get("parse_issues", [])),
            "api_error":           r.get("api_error", ""),
        }

        parsed = r.get("parsed_response", {}) or {}

        # Summary fields
        assessment = parsed.get("overall_assessment", {})
        base["security_rating"] = assessment.get("security_rating", "")
        base["confidence"]      = assessment.get("confidence", "")
        base["summary"]         = assessment.get("summary", "")

        # Security properties (flatten)
        props = parsed.get("security_properties", {})
        for prop in ["confidentiality", "authentication", "integrity",
                     "non_repudiation", "forward_secrecy", "replay_protection"]:
            p = props.get(prop, {})
            base[f"{prop}_supported"]     = p.get("supported", "")
            base[f"{prop}_justification"] = p.get("justification", "")

        # Vulnerabilities (compact)
        vulns = parsed.get("vulnerabilities", [])
        base["vulnerability_count"] = len(vulns)
        base["vulnerabilities_summary"] = " | ".join(
            f"{v.get('id','?')}:{v.get('name','?')}({v.get('severity','?')})"
            for v in vulns
        )

        # Protocol summary
        proto_sum = parsed.get("protocol_summary", {})
        base["participants"]           = ", ".join(proto_sum.get("participants", []))
        base["message_count"]          = proto_sum.get("message_count", "")
        base["cryptographic_primitives"] = ", ".join(proto_sum.get("cryptographic_primitives", []))

        csv_rows.append(base)

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
