"""
input_guardrails_presidio.py
-----------------------------
An NER-based alternative to the regex-based `mask_sensitive_data()` in
guardrails/input_guardrails.py, using Microsoft Presidio.

Why this exists:
Regex only catches PII that follows a fixed shape (emails, SSNs, card
numbers). It misses PII that doesn't -- names, physical addresses, dates
of birth, etc. Presidio uses an NLP/NER model (spaCy) to detect a much
broader set of entity types, then anonymizes them.

Trade-off: this is heavier (extra dependencies + a spaCy language model)
and slower than regex, since every call runs a full NLP pipeline. In
production it's common to run both: regex for cheap, guaranteed patterns,
and an NER-based pass like this as an additional layer -- not a
replacement.

Setup:
    pip install presidio-analyzer presidio-anonymizer
    python -m spacy download en_core_web_lg

Usage is a drop-in replacement for mask_sensitive_data() -- same
GuardrailResult return type -- so you can swap it into
run_input_guardrails() in guardrails/input_guardrails.py if you want
NER-based masking instead of (or in addition to) regex.
"""

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from common import GuardrailResult

# Engines are expensive to build (they load the NLP model), so build them
# once at import time rather than per-call.
_analyzer = AnalyzerEngine()
_anonymizer = AnonymizerEngine()

# Full redaction for most PII, partial masking for emails (domain stays
# visible). Each key in an `operators` dict must be UNIQUE -- listing
# "DEFAULT" twice silently drops the first entry, since it's a plain
# Python dict literal. Give each entity type its own key instead.
DEFAULT_OPERATORS = {
    "DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED>"}),
    "EMAIL_ADDRESS": OperatorConfig(
        "mask", {"type": "mask", "masking_char": "*", "chars_to_mask": 10, "from_end": False}
    ),
}


def detect_pii(text: str, language: str = "en"):
    """Step 1: run NER-based PII detection and return the raw Presidio results."""
    return _analyzer.analyze(text=text, language=language)


def mask_sensitive_data_presidio(text: str, language: str = "en", operators: dict = None) -> GuardrailResult:
    """
    Step 1 (detect) + Step 2 (anonymize), wrapped in the same
    GuardrailResult interface as every other guardrail in this lab.
    Pass a custom `operators` dict to override the default redaction policy.
    """
    results = detect_pii(text, language=language)

    if not results:
        return GuardrailResult(
            passed=True,
            guardrail_name="mask_sensitive_data_presidio",
            reason="No PII detected",
            redacted_text=text,
        )

    anonymized = _anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators or DEFAULT_OPERATORS,
    )

    found_types = sorted({r.entity_type for r in results})
    return GuardrailResult(
        passed=True,  # sanitize-and-continue, same policy as the regex version
        guardrail_name="mask_sensitive_data_presidio",
        reason=f"Redacted: {', '.join(found_types)}",
        category="PII",
        redacted_text=anonymized.text,
    )


if __name__ == "__main__":
    sample = (
        "My name is Sanjay Kumar, my email is sanjay@example.com "
        "and my credit Card Number is 1111222233334444."
    )

    print("Step 1: Detect PII")
    for r in detect_pii(sample):
        print(f"  {r.entity_type}: '{sample[r.start:r.end]}' (score={r.score:.2f})")

    print("\nStep 2: Full guardrail result")
    result = mask_sensitive_data_presidio(sample)
    print(result)
    print(" ->", result.redacted_text)
