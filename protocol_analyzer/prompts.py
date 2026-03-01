"""
Prompt templates and JSON response schema for security protocol analysis.
Keeping prompts in one file makes it easy to iterate for your research.
"""

# ── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert in cryptographic security protocol analysis 
with deep knowledge of formal security verification, attack patterns (man-in-the-middle, 
replay attacks, reflection attacks, type-flaw attacks), and protocol design principles.

Your task is to rigorously analyse security protocols written in Alice-and-Bob (AnB/AnBx) 
notation and return your findings in strict JSON format as specified by the user.

Rules:
- Be precise and technical in your analysis.
- Do NOT infer protocol names from the specification text to avoid bias.
- Base your analysis solely on the protocol structure provided.
- Always populate every field in the JSON schema, even if the value is an empty list or "N/A".
"""

# ── Analysis prompt template ─────────────────────────────────────────────────
ANALYSIS_PROMPT_TEMPLATE = """Analyse the following security protocol specification 
written in Alice-and-Bob notation:

--- PROTOCOL SPECIFICATION ---
{protocol_text}
--- END SPECIFICATION ---

Return your analysis ONLY as a valid JSON object matching this exact schema.
Do not include markdown code fences, explanations, or any text outside the JSON.

JSON SCHEMA:
{{
  "protocol_summary": {{
    "participants": ["list of protocol participants, e.g. Alice, Bob, Server"],
    "goals": ["list of stated or implied security goals, e.g. mutual authentication"],
    "message_count": <integer: number of protocol messages>,
    "cryptographic_primitives": ["list of crypto primitives used, e.g. RSA, AES, Hash"]
  }},

  "security_properties": {{
    "confidentiality": {{
      "supported": <true | false | "partial">,
      "justification": "<explain why or why not>"
    }},
    "authentication": {{
      "supported": <true | false | "partial">,
      "justification": "<explain why or why not>"
    }},
    "integrity": {{
      "supported": <true | false | "partial">,
      "justification": "<explain why or why not>"
    }},
    "non_repudiation": {{
      "supported": <true | false | "partial">,
      "justification": "<explain why or why not>"
    }},
    "forward_secrecy": {{
      "supported": <true | false | "partial">,
      "justification": "<explain why or why not>"
    }},
    "replay_protection": {{
      "supported": <true | false | "partial">,
      "justification": "<explain why or why not>"
    }}
  }},

  "vulnerabilities": [
    {{
      "id": "V-01",
      "name": "<vulnerability name>",
      "type": "<attack type: MITM | Replay | Reflection | Type-Flaw | Impersonation | Other>",
      "severity": "<Critical | High | Medium | Low>",
      "affected_messages": ["M1", "M2"],
      "description": "<detailed technical description of the attack>",
      "attack_trace": "<step-by-step trace of how an attacker (Mallory) would exploit this>",
      "mitigation": "<recommended fix or countermeasure>"
    }}
  ],

  "formal_verification_hints": {{
    "suggested_tools": ["OFMC", "ProVerif", "Scyther", "Tamarin"],
    "suggested_lemmas": ["<list of formal properties to verify, e.g. aliveness, secrecy of Na>"],
    "anticipated_result": "<brief prediction of what a formal tool would likely conclude>"
  }},

  "overall_assessment": {{
    "security_rating": "<Secure | Likely Secure | Weak | Broken>",
    "confidence": "<High | Medium | Low>",
    "summary": "<2-4 sentence overall verdict>",
    "recommendations": ["<list of actionable recommendations>"]
  }}
}}
"""

def build_prompt(protocol_text: str) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt) for an LLM call.
    The protocol name is stripped from the text before sending (bias prevention).
    """
    cleaned = _strip_protocol_name(protocol_text)
    user_prompt = ANALYSIS_PROMPT_TEMPLATE.format(protocol_text=cleaned)
    return SYSTEM_PROMPT, user_prompt


def _strip_protocol_name(text: str) -> str:
    """
    Remove the first line if it contains 'Protocol:' to prevent LLM
    from using the well-known name to recall memorised analyses.
    """
    lines = text.strip().splitlines()
    filtered = [
        line for line in lines
        if not line.strip().lower().startswith("protocol:")
    ]
    return "\n".join(filtered).strip()
