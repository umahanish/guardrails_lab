# Agentic AI Guardrails Lab (Claude)

A hands-on implementation of the guardrail architecture diagram:
**Input Guardrails → Agent/LLM → Output Guardrails**, plus **Tool
Guardrails** sitting between the Agent and its Tools.

Start with `THEORY.md` — it explains the concepts behind every guardrail
before you touch code. The full guided lab (including the alternative
implementations below and a token-cost walkthrough) lives in
`guardrails_lab.ipynb`; `main.py` is a lighter, script-only way to see the
core pipeline run.

![Guardrails architecture diagram: Input Guardrails (Mask Sensitive Data, Detect Prompt Injection, Scope Validation, Content Safety) feed the Agent/LLM loop, which feeds Output Guardrails (Groundedness/Hallucination check, Mask Sensitive Data, Content Safety) back to the Agent; the Agent also reaches Tools (Read/Write/Update/Delete) through Tool Guardrails (Schema/Parameter validation, Permission enforcement).](architecture_diagram.svg)

## What's implemented

| Diagram box | File | Function(s) |
|---|---|---|
| Mask Sensitive Data (input) | `guardrails/input_guardrails.py` | `mask_sensitive_data` |
| Detect Prompt Injection | `guardrails/input_guardrails.py` | `detect_prompt_injection` |
| Scope Validation | `guardrails/input_guardrails.py` | `scope_validation` |
| Content Safety (input) | `guardrails/input_guardrails.py` | `content_safety` |
| Groundedness / Hallucination check | `guardrails/output_guardrails.py` | `groundedness_check` |
| Mask Sensitive Data (output) | `guardrails/output_guardrails.py` | reuses `mask_sensitive_data` |
| Content Safety (output) | `guardrails/output_guardrails.py` | reuses `content_safety` |
| Schema / Parameter validation | `guardrails/tool_guardrails.py` | `validate_schema` |
| Permission enforcement | `guardrails/tool_guardrails.py` | `check_permission` |
| Agent | `agent.py` | `Agent` class |
| Tools (Read/Write/Update/Delete) | `tools.py` | `TOOL_REGISTRY` |

Two guardrail "flavors" are used, deliberately, so students see both:
- **Deterministic** (regex / JSON schema / allow-lists): masking, schema
  validation, permission checks — fast and 100% reproducible.
- **LLM-as-judge** (a Claude call that must return strict JSON):
  prompt-injection detection, scope validation, content safety,
  groundedness — catches nuance that regex can't.

### Alternative / drop-in guardrail implementations

Each core guardrail above also has one or more alternative implementations,
each demonstrating a different trade-off (local model vs. API call, regex
vs. NER, cost/latency vs. reasoning depth). These are optional layers, not
replacements — the module docstring in each file explains the trade-off in
depth, and section 8 of the notebook measures the cost difference directly.

| Alternative to | File | Approach |
|---|---|---|
| `detect_prompt_injection` | `guardrails/input_guardrails_deberta.py` | Local DeBERTa-v3 classifier (ProtectAI) — no API call, millisecond latency |
| `content_safety` (input) | `guardrails/input_guardrails_detoxify.py` | Local Detoxify classifier — per-category toxicity scores |
| `scope_validation` | `guardrails/input_guardrails_groq.py` | Groq-hosted `openai/gpt-oss-120b` — fast/cheap model-routing example |
| `mask_sensitive_data` | `guardrails/input_guardrails_presidio.py` | Microsoft Presidio NER — catches PII with no fixed shape (names, addresses) |
| `mask_sensitive_data` (reversible) | `guardrails/pii_tokenization.py` | Presidio + AES encryption — lets a tool decrypt the real value after guardrails approve, instead of destroying it with a fixed placeholder |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your ANTHROPIC_API_KEY
python main.py
```

Optional dependencies for the alternative implementations above
(presidio, transformers/torch, detoxify, groq) are listed separately in
`requirements.txt` — install only the ones you need.

To run the full guided lab instead: `jupyter notebook guardrails_lab.ipynb`.

## Project structure

```
guardrails_lab/
├── THEORY.md                       # Read first — concepts behind every guardrail
├── TOKENS_THEORY.md                # Companion theory for notebook section 8 (token/cost types)
├── guardrails_lab.ipynb            # Full guided lab: every guardrail + alternatives + token-cost exercises
├── common.py                       # Anthropic client, GuardrailResult, LLM-judge helper
├── agent.py                        # Wires input/output/tool guardrails around the LLM call
├── tools.py                        # Mock Read/Write/Update/Delete tools
├── guardrails/
│   ├── input_guardrails.py
│   ├── input_guardrails_deberta.py     # Alternative: local prompt-injection classifier
│   ├── input_guardrails_detoxify.py    # Alternative: local content-safety classifier
│   ├── input_guardrails_groq.py        # Alternative: Groq-hosted scope validation
│   ├── input_guardrails_presidio.py    # Alternative: NER-based PII masking
│   ├── pii_tokenization.py             # Alternative: reversible (encrypted) PII masking
│   ├── output_guardrails.py
│   └── tool_guardrails.py
├── main.py                         # Run this — demonstrates every core guardrail
├── exercises.md                    # Student TODOs (also embedded in the notebook, section 9)
├── requirements.txt
└── .env.example
```

## Suggested lab flow for students

1. Read `THEORY.md`.
2. Run `main.py` and read the console output next to the diagram — or work
   through `guardrails_lab.ipynb` for the full guided version.
3. Open `guardrails/input_guardrails.py` and trace how `run_input_guardrails()`
   calls each of the four checks in order and stops at the first block.
4. Open `guardrails/output_guardrails.py` and do the same for the three
   output checks.
5. Open `guardrails/tool_guardrails.py` and `agent.py`'s `call_tool()` to see
   how a *role* (viewer/editor/admin) restricts which tools can run.
6. Skim the alternative implementations in `guardrails/` to see the same
   guardrail solved a different way (local model, NER, different provider).
7. Read `TOKENS_THEORY.md` and work through notebook section 8 to see how
   guardrail choices (Claude-as-judge vs. local classifier, caching, etc.)
   affect token cost.
8. Complete `exercises.md`.

## Key teaching point

Guardrails should **fail closed**: if a check errors out or the judge
model returns unparseable output (see `ask_claude_judge()` in `common.py`),
treat that as "flagged" rather than silently letting the request through.
