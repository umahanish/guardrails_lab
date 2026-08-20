"""
tool_guardrails.py
-------------------
Implements the "Tool Guardrails" box in the diagram, which sits between the
Agent and its Tools (Read/Write/Update/Delete):

  1. validate_schema   - deterministic JSON-schema validation of tool
                          parameters before execution
  2. check_permission  - deterministic allow-list check: is this
                          role/user allowed to call this tool at all?

Both are deterministic (no LLM call) because tool execution is where
mistakes become *real side effects* (deleting data, sending messages) —
this is exactly the kind of check you want to be 100% reliable, not
probabilistic.
"""

from typing import Any, Dict
import jsonschema
from common import GuardrailResult

# Example schemas for the tools in the diagram (Read/Write/Update/Delete).
# In a real system these would live next to each tool's definition.
TOOL_SCHEMAS: Dict[str, dict] = {
    "read": {
        "type": "object",
        "properties": {"record_id": {"type": "string"}},
        "required": ["record_id"],
        "additionalProperties": False,
    },
    "write": {
        "type": "object",
        "properties": {
            "record_id": {"type": "string"},
            "data": {"type": "object"},
        },
        "required": ["record_id", "data"],
        "additionalProperties": False,
    },
    "update": {
        "type": "object",
        "properties": {
            "record_id": {"type": "string"},
            "fields": {"type": "object"},
        },
        "required": ["record_id", "fields"],
        "additionalProperties": False,
    },
    "delete": {
        "type": "object",
        "properties": {"record_id": {"type": "string"}},
        "required": ["record_id"],
        "additionalProperties": False,
    },
}

# Example role -> allowed tools map. Note "delete" is deliberately
# restricted, mirroring least-privilege access control in real systems.
ROLE_PERMISSIONS: Dict[str, list] = {
    "viewer": ["read"],
    "editor": ["read", "write", "update"],
    "admin": ["read", "write", "update", "delete"],
}


def validate_schema(tool_name: str, params: Dict[str, Any]) -> GuardrailResult:
    """Validate `params` against the JSON schema registered for `tool_name`."""
    schema = TOOL_SCHEMAS.get(tool_name)
    if schema is None:
        return GuardrailResult(
            passed=False,
            guardrail_name="validate_schema",
            reason=f"No schema registered for unknown tool '{tool_name}'",
            category="UNKNOWN_TOOL",
        )

    try:
        jsonschema.validate(instance=params, schema=schema)
    except jsonschema.ValidationError as e:
        return GuardrailResult(
            passed=False,
            guardrail_name="validate_schema",
            reason=f"Invalid parameters for '{tool_name}': {e.message}",
            category="SCHEMA_ERROR",
        )

    return GuardrailResult(
        passed=True,
        guardrail_name="validate_schema",
        reason=f"Parameters valid for '{tool_name}'",
    )


def check_permission(tool_name: str, role: str) -> GuardrailResult:
    """Check whether `role` is allowed to call `tool_name` at all."""
    allowed_tools = ROLE_PERMISSIONS.get(role, [])
    if tool_name not in allowed_tools:
        return GuardrailResult(
            passed=False,
            guardrail_name="check_permission",
            reason=f"Role '{role}' is not permitted to call '{tool_name}'",
            category="PERMISSION_DENIED",
        )

    return GuardrailResult(
        passed=True,
        guardrail_name="check_permission",
        reason=f"Role '{role}' permitted to call '{tool_name}'",
    )


def run_tool_guardrails(tool_name: str, params: Dict[str, Any], role: str):
    """Runs schema validation then permission enforcement, in that order."""
    results = [validate_schema(tool_name, params)]
    if not results[-1].passed:
        return results

    results.append(check_permission(tool_name, role))
    return results
