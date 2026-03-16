"""
Prompt templates and JSON response schema for security protocol analysis.
Keeping prompts in one file makes it easy to iterate for your research.
 
Extraction helpers
------------------
extract_protocol_name(text)  → str   – protocol name from "Protocol:" line
extract_ofmc_results(text)   → list  – parsed OFMC result rows
prepare_for_llm(text)        → str   – cleaned text safe to send to an LLM
                                       (name + comments + OFMC block stripped)
"""
 
import re
from typing import Optional
 
 
# ── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert in cryptographic security protocol analysis \
with deep knowledge of formal security verification, attack patterns \
(man-in-the-middle, replay attacks, reflection attacks, type-flaw attacks), \
and protocol design principles.
 
Your task is to analyse security protocols written in Alice-and-Bob (AnB/AnBx) \
notation and determine, for every security goal declared in the protocol, whether \
a symbolic model-checker such as OFMC would find an attack or not.
 
Rules:
- Be precise and technical in your analysis.
- Do NOT infer the protocol name from the specification text to avoid bias.
- Base your verdict solely on the protocol structure provided.
- Every declared goal in the protocol MUST appear as a separate entry in your response.
- Use exactly the verdict strings: "ATTACK", "NO_ATTACK", or "unknown".
- "unknown" is only allowed when the goal cannot be determined from the specification alone.
"""
 
# ── Analysis prompt template ─────────────────────────────────────────────────
ANALYSIS_PROMPT_TEMPLATE = """Analyse the following security protocol specification \
written in Alice-and-Bob notation:
 
--- PROTOCOL SPECIFICATION ---
{protocol_text}
--- END SPECIFICATION ---
 
Identify every security goal declared or implied by this protocol.
For each goal, determine whether a symbolic model-checker (e.g. OFMC) would find
an attack on that goal.
 
Return your analysis ONLY as a valid JSON object with this exact structure.
Do NOT include markdown code fences, explanations, or any text outside the JSON.
 
JSON SCHEMA:
{{
  "goals": [
    {{
      "attack":       "<ATTACK | NO_ATTACK | unknown>",
      "number_goals": 0 or 1,  # must be 1 for every entry; never counts >1
      "goal":         "<copy the exact goal line verbatim from the protocol, e.g. 'B authenticates A on NB'>"
    }}
  ]
}}
 
Rules for the "goals" array:
- One entry per security goal.  Never merge multiple goals into one entry.
- "attack"       must be exactly one of: "ATTACK", "NO_ATTACK", "unknown"
  · "ATTACK"     – a concrete attack trace exists against this goal
  · "NO_ATTACK"  – no attack found; the goal holds in the symbolic model
  · "unknown"    – insufficient information to decide
- "number_goals" is the number of goals identified in the protocol specification.  
- "goal"         must be the verbatim line (or clause) copied directly from the protocol
                 specification that declares this goal — do NOT paraphrase or generate a
                 description.  Use an empty string only when the specification contains
                 no goal text at all (this should be extremely rare). The goal is to get
                 the line that make this protocol to be an attack or no-attack, so the LLM should copy it verbatim.
 

Cryptographic Primitives
  • Asymmetric encryption:
  – inv(K) – the private key corresponding to public key K.
  – {{Msg}}K or {{Msg}}inv(K) – encryption of Msg with a public or private key.
  • Symmetric encryption:
  – {{|Msg|}}K – encryption of Msg with a symmetric key K.
  • Common functions:
  – pk(A) – public encryption key of agent A (for confidentiality).
  – inv(pk(A)) – corresponding private decryption key of A.
  – sk(A) – public verification key of agent A (for authentication).
  – inv(sk(A)) – corresponding private signing key of A.
  – hash(Msg) – a cryptographic digest (fingerprint) of Msg.
  – hmac(Msg,K) – keyed-hash message authentication code of Msg using key K.

"""

# ── Public helpers ────────────────────────────────────────────────────────────
 
def extract_protocol_name(text: str) -> str:
    """
    Return the protocol name from the first line matching 'Protocol: <name>'.
    Falls back to an empty string if no such line is found.
 
    Handles both plain lines and comment-prefixed lines, e.g.:
        Protocol: NSL
        % Protocol: NSL
    """
    for line in text.splitlines():
        stripped = line.strip().lstrip("%").strip()
        if stripped.lower().startswith("protocol:"):
            name = stripped[len("protocol:"):].strip()
            return name
    return ""
 
 
def extract_ofmc_results(text: str) -> list:
    """
    Parse OFMC-style result rows embedded in the protocol file.
 
    Recognised formats (with or without leading '%' comment marker):
        attack\\tnumber-goals\\tgoal          ← header row (skipped)
        NO_ATTACK\\t1\\tB authenticates A …
        ATTACK\\t1\\tB *->* A: NB2
        unknown\\t0\\t
 
    Each returned dict has:
        {
          "attack":       str,   e.g. "NO_ATTACK" | "ATTACK" | "unknown"
          "number_goals": int,
          "goal":         str    (may be empty)
        }
    """
    # Regex: optional leading comment marker, then verdict TAB count TAB? goal?
    row_pattern = re.compile(
        r"^[%#\s]*"                         # optional comment prefix / whitespace
        r"(ATTACK|NO_ATTACK|unknown)"        # verdict
        r"\t(\d+)"                           # tab + number-goals
        r"(?:\t(.*))?$",                     # optional tab + goal text
        re.IGNORECASE,
    )
 
    rows = []
    for line in text.splitlines():
        m = row_pattern.match(line)
        if m:
            rows.append({
                "attack":       m.group(1).upper(),
                "number_goals": int(m.group(2)),
                "goal":         (m.group(3) or "").strip(),
            })
    return rows
 
 
def prepare_for_llm(text: str) -> str:
    """
    Return a cleaned version of the protocol text that is safe to send to an LLM:
      - Removes 'Protocol:' name line (bias prevention)
      - Removes all comment lines (lines whose first non-whitespace char is '%')
      - Strips blank lines that result from the above removals
    """
    lines = text.strip().splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Drop protocol name line
        if stripped.lower().startswith("protocol:"):
            continue
        # Drop comment lines (AnBx uses % for comments)
        if stripped.startswith("%"):
            continue
        cleaned.append(line)
 
    # Collapse consecutive blank lines to one
    result_lines = []
    prev_blank = False
    for line in cleaned:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        result_lines.append(line)
        prev_blank = is_blank
 
    return "\n".join(result_lines).strip()
 
 
def build_prompt(protocol_text: str) -> tuple:
    """
    Returns (system_prompt, user_prompt, protocol_name) for an LLM call.

    The protocol name is extracted from the raw text BEFORE prepare_for_llm
    strips the 'Protocol:' line and all comment lines, so the name is never
    lost.  Callers should use the returned name rather than trying to extract
    it again from the cleaned text.

    Returns:
        (system_prompt: str, user_prompt: str, protocol_name: str)
    """
    # 1. Save the name from raw text BEFORE any stripping
    protocol_name = extract_protocol_name(protocol_text)

    # 2. Strip name + comments so the LLM cannot be biased by the name
    cleaned = prepare_for_llm(protocol_text)

    user_prompt = ANALYSIS_PROMPT_TEMPLATE.format(protocol_text=cleaned)
    return SYSTEM_PROMPT, user_prompt, protocol_name
 
 
# ── Legacy alias (kept for backwards compatibility) ───────────────────────────
def _strip_protocol_name(text: str) -> str:
    return prepare_for_llm(text)
