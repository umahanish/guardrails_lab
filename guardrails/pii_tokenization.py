"""
pii_tokenization.py
--------------------
Reversible PII tokenization: PII is ENCRYPTED (not just redacted) before
it ever reaches an LLM. Only the trusted backend -- which holds the AES
key -- can decrypt it back. The LLM (including any LLM-as-judge guardrail
call) only ever sees ciphertext.

This solves the problem plain masking can't: sometimes the agent's actual
job requires the real value downstream (e.g. "look up the record for this
email"). Redacting to "[REDACTED_EMAIL]" destroys that value permanently.
Encrypting instead lets the *tool execution layer* -- which runs after all
guardrails, inside your trust boundary -- decrypt the token back to the
real value right before it's needed, without the LLM ever having seen or
transmitted the plaintext.

    User text
        │
        ▼
    encrypt_pii()  ──►  ciphertext sent to LLM / judges / agent
        │
        │   (key never leaves the backend)
        ▼
    decrypt_pii()  ──►  only called inside a tool, after tool guardrails
                         have already approved the call

Key management note: in this lab the AES key is generated in-process with
os.urandom() purely for demonstration. In production, keys belong in a
secrets manager / KMS, are rotated, and are never logged, printed, hard-
coded, or exposed to the model in any form.
"""

from typing import List
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine, DeanonymizeEngine
from presidio_anonymizer.entities import OperatorConfig, OperatorResult

from common import GuardrailResult

_analyzer = AnalyzerEngine()
_anonymizer = AnonymizerEngine()
_deanonymizer = DeanonymizeEngine()

# AES key size must be 16, 24, or 32 bytes (AES-128/192/256).
AES_KEY_SIZE_BYTES = 16


def encrypt_pii(text: str, key: bytes, language: str = "en"):
    """
    Detects PII and replaces each span with AES ciphertext (not a fixed
    placeholder). Returns (guardrail_result, encrypted_items) --
    `encrypted_items` must be kept (server-side only) to later decrypt.
    """
    results = _analyzer.analyze(text=text, language=language)

    if not results:
        return (
            GuardrailResult(True, "encrypt_pii", "No PII detected", redacted_text=text),
            [],
        )

    encrypted = _anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators={"DEFAULT": OperatorConfig("encrypt", {"key": key})},
    )

    found_types = sorted({r.entity_type for r in results})
    guardrail_result = GuardrailResult(
        passed=True,
        guardrail_name="encrypt_pii",
        reason=f"Encrypted (reversible): {', '.join(found_types)}",
        category="PII",
        redacted_text=encrypted.text,
    )
    return guardrail_result, encrypted.items


def decrypt_pii(encrypted_text: str, items: List[OperatorResult], key: bytes) -> str:
    """
    Restores the original plaintext. Call this ONLY inside the trusted
    tool-execution layer, after tool guardrails have approved the call --
    never inside a prompt sent to the LLM, and never logged.
    """
    restored = _deanonymizer.deanonymize(
        text=encrypted_text,
        entities=items,
        operators={"DEFAULT": OperatorConfig("decrypt", {"key": key})},
    )
    return restored.text


if __name__ == "__main__":
    import os

    key = os.urandom(AES_KEY_SIZE_BYTES)  # demo only -- use a KMS in production
    sample = "My name is Sanjay Kumar, my email is sanjay@example.com."

    result, items = encrypt_pii(sample, key)
    print("Sent to LLM :", result.redacted_text)

    restored = decrypt_pii(result.redacted_text, items, key)
    print("Restored    :", restored)
    print("Round trip OK:", restored == sample)
