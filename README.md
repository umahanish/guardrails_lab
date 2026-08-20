# Agentic AI Guardrails Lab (Claude)

A hands-on implementation of the guardrail architecture diagram:
**Input Guardrails → Agent/LLM → Output Guardrails**, plus **Tool
Guardrails** sitting between the Agent and its Tools.

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

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your ANTHROPIC_API_KEY
python main.py
```

## Project structure

```
guardrails_lab/
├── common.py                       # Anthropic client, GuardrailResult, LLM-judge helper
├── agent.py                        # Wires input/output/tool guardrails around the LLM call
├── tools.py                        # Mock Read/Write/Update/Delete tools
├── guardrails/
│   ├── input_guardrails.py
│   ├── output_guardrails.py
│   └── tool_guardrails.py
├── main.py                         # Run this — demonstrates every guardrail
├── exercises.md                    # Student TODOs
├── requirements.txt
└── .env.example
```

## Suggested lab flow for students

1. Run `main.py` and read the console output next to the diagram.
2. Open `guardrails/input_guardrails.py` and trace how `run_input_guardrails()`
   calls each of the four checks in order and stops at the first block.
3. Open `guardrails/output_guardrails.py` and do the same for the three
   output checks.
4. Open `guardrails/tool_guardrails.py` and `agent.py`'s `call_tool()` to see
   how a *role* (viewer/editor/admin) restricts which tools can run.
5. Complete `exercises.md`.

## Key teaching point

Guardrails should **fail closed**: if a check errors out or the judge
model returns unparseable output (see `ask_claude_judge()` in `common.py`),
treat that as "flagged" rather than silently letting the request through.
