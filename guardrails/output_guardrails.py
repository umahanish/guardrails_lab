"""
output_guardrails.py
---------------------
Implements the three boxes in the "Output Guardrails" stage of the diagram:

  1. groundedness_check - Claude-as-judge: is the LLM's answer supported by
                           the provided context/sources, or is it likely a
                           hallucination?
  2. mask_sensitive_data - reuse the same deterministic PII redaction as
                           the input stage (outputs can leak PII too, e.g.
                           if the LLM echoes data pulled from a tool call).
  3. content_safety      - reuse the same Claude-as-judge classifier as the
                           input stage, applied to the model's own output.
"""

from anthropic import Anthropic
from common import GuardrailResult, ask_claude_judge
from guardrails.input_guardrails import mask_sensitive_data, content_safety  # reuse

# Re-exported so callers only need to import from output_guardrails.py
__all__ = ["groundedness_check", "mask_sensitive_data", "content_safety"]


# ---------------------------------------------------------------------------
# 1. Groundedness / Hallucination Check (LLM-as-judge)
# ---------------------------------------------------------------------------

_GROUNDEDNESS_SYSTEM_PROMPT = """You are a factual-grounding classifier.
You will be given SOURCE_CONTEXT (the only facts the assistant is allowed
to rely on) and an ASSISTANT_ANSWER. Determine whether every factual claim
in ASSISTANT_ANSWER is actually supported by SOURCE_CONTEXT.

Flag the answer if it:
- states facts, numbers, or names not present in SOURCE_CONTEXT
- contradicts SOURCE_CONTEXT
- presents a guess as if it were a confirmed fact

Do NOT flag reasonable summarization, rephrasing, or the assistant saying
"I don't know" / asking a clarifying question.

Respond with ONLY this JSON, no other text:
{"flagged": true|false, "category": "UNGROUNDED"|"GROUNDED", "reason": "<one short sentence>"}"""


def groundedness_check(client: Anthropic, answer: str, source_context: str) -> GuardrailResult:
    """
    `source_context` is whatever the LLM was actually allowed to use to
    produce its answer (retrieved documents, tool outputs, etc). This is
    what the answer is checked against for hallucinations.
    """
    user_content = (
        f"SOURCE_CONTEXT:\n{source_context}\n\n"
        f"ASSISTANT_ANSWER:\n{answer}"
    )
    result = ask_claude_judge(client, _GROUNDEDNESS_SYSTEM_PROMPT, user_content)
    flagged = result.get("flagged", True)
    return GuardrailResult(
        passed=not flagged,
        guardrail_name="groundedness_check",
        reason=result.get("reason", ""),
        category=result.get("category"),
        raw_model_output=result,
    )


# ---------------------------------------------------------------------------
# Convenience: run the full output pipeline in the same order as the diagram
# ---------------------------------------------------------------------------

def run_output_guardrails(client: Anthropic, answer: str, source_context: str):
    """
    Runs all three output guardrails in order and stops early on the first
    hard block. Returns (final_text, list_of_results).

    Order matches the diagram: Groundedness -> Mask -> Content Safety.
    """
    results = []

    ground_result = groundedness_check(client, answer, source_context)
    results.append(ground_result)
    if not ground_result.passed:
        return answer, results

    mask_result = mask_sensitive_data(answer)
    results.append(mask_result)
    working_text = mask_result.redacted_text

    safety_result = content_safety(client, working_text)
    results.append(safety_result)

    return working_text, results
