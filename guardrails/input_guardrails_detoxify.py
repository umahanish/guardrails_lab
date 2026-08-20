"""
input_guardrails_detoxify.py
------------------------------
A local-model alternative to the Claude-as-judge `content_safety()` in
guardrails/input_guardrails.py, using Unitary's Detoxify library.

Why this exists:
Same rationale as the DeBERTa prompt-injection module: a small, dedicated,
locally-run toxicity classifier runs in milliseconds on-device with zero
per-call API cost, and gives per-category scores (toxicity, threats,
insults, identity attacks, etc.) rather than a single flagged/not-flagged
verdict -- useful when you want to log *why* something was blocked, or
apply different thresholds per category.

Trade-off: like any fixed classifier, it only knows the categories and
patterns it was trained on. It won't catch novel or context-dependent
harm the way an LLM judge -- which can actually reason about intent --
can. In production it's common to run both and block if either flags.

Setup:
    pip install detoxify

The 'original' checkpoint is trained on the Jigsaw Toxic Comment
Classification dataset and scores six categories: toxicity,
severe_toxicity, obscene, threat, insult, identity_attack. (Detoxify also
offers 'unbiased' and 'multilingual' checkpoints -- see the project's
README for the full comparison.)
"""

from detoxify import Detoxify
from common import GuardrailResult

TOXICITY_THRESHOLD = 0.5

# Loading downloads/loads model weights, so build it once at import time.
_detoxify_model = Detoxify("original")


def content_safety_detoxify(text: str, threshold: float = TOXICITY_THRESHOLD) -> GuardrailResult:
    """
    Scores `text` across Detoxify's toxicity categories. Same
    GuardrailResult interface as content_safety() in input_guardrails.py,
    so it's a drop-in swap (or an additional layer) inside
    run_input_guardrails().
    """
    scores = _detoxify_model.predict(text)  # dict[str, float] for a single string
    flagged_categories = {label: score for label, score in scores.items() if score >= threshold}
    flagged = bool(flagged_categories)

    reason = (
        ", ".join(f"{label}={score:.3f}" for label, score in flagged_categories.items())
        if flagged
        else "No toxic content detected"
    )

    return GuardrailResult(
        passed=not flagged,
        guardrail_name="content_safety_detoxify",
        reason=reason,
        category="TOXIC" if flagged else "NONE",
        raw_model_output=scores,
    )


if __name__ == "__main__":
    import pandas as pd

    texts = [
        "Thanks so much for your help, this was great!",
        "You're a disgusting idiot and everyone hates you.",
        "I will find you and make you regret this.",
        "This movie was boring, not my taste.",
    ]

    results = _detoxify_model.predict(texts)
    df = pd.DataFrame(results, index=texts).round(3)
    print(df)

    print("\nWrapped as GuardrailResult:")
    for text in texts:
        print(content_safety_detoxify(text), "|", text)
