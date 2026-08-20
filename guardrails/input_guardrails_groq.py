"""
input_guardrails_groq.py
--------------------------
A fast/cheap-provider alternative to the Claude-as-judge `scope_validation()`
in guardrails/input_guardrails.py, using Groq's hosted inference
(openai/gpt-oss-120b at low reasoning effort).

Why this exists:
Scope validation is a simple triage task -- "does this request belong to
this agent's job or not" -- not one that needs deep reasoning. Routing
simple classification calls to a fast, cheap inference provider (rather
than the same large model used for the agent's actual answer) is a
concrete instance of the model-routing cost strategy: use the cheapest
tool that reliably does the job, and save your most capable/expensive
model for turns that actually need it.

Trade-off: this adds a second provider to your stack (a second API key,
a second dependency, a second point of failure/latency variance), and a
different model family may have different blind spots than Claude on
edge cases. As with every alternative guardrail in this lab, the pattern
is "additional/comparable layer," not a blind swap -- validate on your
own scope-boundary test cases before relying on it in production.

Setup:
    pip install groq
    Get a key at https://console.groq.com
"""

import json
from groq import Groq
from common import GuardrailResult

GROQ_MODEL = "openai/gpt-oss-120b"


def classify_scope_groq(query: str, scope_description: str, api_key: str = None) -> GuardrailResult:
    """
    Same GuardrailResult interface as scope_validation() in
    input_guardrails.py, so it's a drop-in swap (or a second, cheaper
    layer) inside run_input_guardrails().
    """
    client = Groq(api_key=api_key)

    system_prompt = f"""You are a scope-restriction guardrail for an LLM application.
{scope_description}
Decide if the user query is in-scope or off-topic.
Respond ONLY with JSON, no other text:
{{"flagged": true/false, "confidence": 0.0-1.0, "reason": "short reason"}}
flagged=true means OFF-TOPIC (should be blocked)."""

    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        reasoning_effort="low",  # fast, cheap -- this is a simple triage task
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
    )

    raw_text = completion.choices[0].message.content
    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        result = {"flagged": True, "confidence": 0.0, "reason": f"Judge model returned non-JSON output: {raw_text[:200]}"}

    flagged = result.get("flagged", True)
    return GuardrailResult(
        passed=not flagged,
        guardrail_name="classify_scope_groq",
        reason=result.get("reason", ""),
        category="OUT_OF_SCOPE" if flagged else "IN_SCOPE",
        raw_model_output=result,
    )


if __name__ == "__main__":
    scope = (
        "This is a banking customer support assistant. In scope:\n"
        "- account balance and transaction queries\n"
        "- password/login/net-banking help\n"
        "- card and loan related questions\n"
        "Out of scope: general knowledge, coding help, creative writing, "
        "weather, or anything unrelated to this bank's services."
    )

    test_queries = [
        "What's my account balance?",
        "Can you help me reset my net-banking password?",
        "Write me a Python script to scrape a website.",
        "What's the weather like today?",
    ]

    for q in test_queries:
        r = classify_scope_groq(q, scope)
        print(r, "|", q)
