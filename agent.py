"""
agent.py
--------
Wires the full diagram together:

  User -> Input Guardrails -> Agent -> LLM -> Output Guardrails -> User
                                 |
                                 v
                          Tool Guardrails -> Tools

This is a simplified educational version: the "LLM" call is a single
Claude request, and tool-calling is triggered by a lightweight convention
(the model can respond with a JSON block asking for a tool) rather than
full native tool-use, so students can see every guardrail step clearly
in the console output.
"""

import json
from dataclasses import dataclass
from typing import List

from common import get_client, GUARDRAIL_MODEL, GuardrailResult
from guardrails.input_guardrails import run_input_guardrails
from guardrails.output_guardrails import run_output_guardrails
from guardrails.tool_guardrails import run_tool_guardrails
from tools import TOOL_REGISTRY

AGENT_SCOPE = "Answer questions about employee records using the Read/Write/Update/Delete tools only."

_AGENT_SYSTEM_PROMPT = f"""You are an internal HR records assistant.
Your job: {AGENT_SCOPE}
Only use facts given to you in this conversation. If you don't know
something, say so instead of guessing."""


@dataclass
class AgentTurnResult:
    final_response: str
    blocked: bool
    blocked_at: str = ""
    input_guardrail_results: List[GuardrailResult] = None
    output_guardrail_results: List[GuardrailResult] = None


class Agent:
    def __init__(self, role: str = "viewer"):
        self.client = get_client()
        self.role = role

    def handle_message(self, user_message: str) -> AgentTurnResult:
        # --- 1. INPUT GUARDRAILS -------------------------------------------------
        safe_text, input_results = run_input_guardrails(
            self.client, user_message, allowed_scope=AGENT_SCOPE
        )
        if any(not r.passed for r in input_results):
            failed = next(r for r in input_results if not r.passed)
            return AgentTurnResult(
                final_response=f"Request blocked by input guardrail: {failed}",
                blocked=True,
                blocked_at="input",
                input_guardrail_results=input_results,
            )

        # --- 2. AGENT / LLM CALL --------------------------------------------------
        response = self.client.messages.create(
            model=GUARDRAIL_MODEL,
            max_tokens=500,
            system=_AGENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": safe_text}],
        )
        llm_answer = "".join(b.text for b in response.content if b.type == "text")

        # In a full implementation, tool calls detected here would run
        # through run_tool_guardrails() before touching tools.py. See
        # exercises.md for a hands-on version of that step.

        # --- 3. OUTPUT GUARDRAILS ---------------------------------------------
        final_text, output_results = run_output_guardrails(
            self.client, llm_answer, source_context=safe_text
        )
        if any(not r.passed for r in output_results):
            failed = next(r for r in output_results if not r.passed)
            return AgentTurnResult(
                final_response=f"Response blocked by output guardrail: {failed}",
                blocked=True,
                blocked_at="output",
                input_guardrail_results=input_results,
                output_guardrail_results=output_results,
            )

        return AgentTurnResult(
            final_response=final_text,
            blocked=False,
            input_guardrail_results=input_results,
            output_guardrail_results=output_results,
        )

    def call_tool(self, tool_name: str, params: dict):
        """Demonstrates the Tool Guardrails box directly (Agent -> Tool Guardrails -> Tools)."""
        results = run_tool_guardrails(tool_name, params, self.role)
        if any(not r.passed for r in results):
            failed = next(r for r in results if not r.passed)
            return {"blocked": True, "reason": str(failed)}, results

        tool_fn = TOOL_REGISTRY[tool_name]
        return tool_fn(**params), results
