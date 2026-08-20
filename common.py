"""
common.py
---------
Shared utilities used by every guardrail in the lab:

  - `get_client()`      -> a configured Anthropic client
  - `GuardrailResult`    -> the standard return type for every guardrail check
  - `ask_claude_judge()` -> a helper that asks Claude to act as a strict
                            JSON-only classifier (used by every "LLM-based"
                            guardrail: prompt injection, scope, content
                            safety, groundedness, etc.)

Teaching note for students:
Guardrails generally come in two flavors:
  1. Deterministic / rule-based  (regex, schema validation, allow-lists)
     -> fast, cheap, 100% reproducible, but can't catch nuance.
  2. Model-based ("LLM-as-judge")
     -> catches nuance and paraphrased attacks, but costs a call and can
        occasionally be wrong -- so it should never be your ONLY safety net
        for a truly high-stakes check.
A good guardrail pipeline usually layers both.
"""

import os
import json
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

# The model used for all guardrail judgments in this lab. Small/fast models
# are usually good enough for classification tasks like these.
GUARDRAIL_MODEL = "claude-sonnet-4-6"


def get_client() -> Anthropic:
    """Return an Anthropic client using ANTHROPIC_API_KEY from the environment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key."
        )
    return Anthropic(api_key=api_key)


@dataclass
class GuardrailResult:
    """Standard result object every guardrail function returns."""
    passed: bool
    guardrail_name: str
    reason: str = ""
    category: Optional[str] = None          # e.g. "PII", "INJECTION", "UNSAFE"
    redacted_text: Optional[str] = None      # populated by masking guardrails
    raw_model_output: Optional[dict] = field(default=None, repr=False)

    def __str__(self):
        status = "PASS" if self.passed else "BLOCK"
        return f"[{status}] {self.guardrail_name}: {self.reason}"


def ask_claude_judge(client: Anthropic, system_prompt: str, user_content: str) -> dict:
    """
    Ask Claude to act as a strict JSON-only classifier.

    `system_prompt` must instruct Claude to answer with ONLY a JSON object
    (no markdown fences, no extra text). This helper parses that JSON and
    returns it as a dict. If parsing fails, it returns a safe fallback dict
    that flags the content for manual review instead of crashing.
    """
    response = client.messages.create(
        model=GUARDRAIL_MODEL,
        max_tokens=300,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    raw_text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    # Defensive parsing: strip markdown fences if the model adds them anyway.
    cleaned = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "flagged": True,
            "category": "PARSE_ERROR",
            "reason": f"Judge model returned non-JSON output: {raw_text[:200]}",
        }
