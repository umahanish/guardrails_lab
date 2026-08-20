"""
tools.py
--------
Tiny in-memory "database" and the four tools shown in the diagram
(Read / Write / Update / Delete). These are intentionally simple so
students can focus on the guardrail logic, not the tool implementation.
"""

_FAKE_DB = {
    "1": {"name": "Ada Lovelace", "role": "engineer"},
    "2": {"name": "Grace Hopper", "role": "engineer"},
}


def read(record_id: str):
    return _FAKE_DB.get(record_id, {"error": "not found"})


def write(record_id: str, data: dict):
    _FAKE_DB[record_id] = data
    return {"status": "created", "record_id": record_id}


def update(record_id: str, fields: dict):
    if record_id not in _FAKE_DB:
        return {"error": "not found"}
    _FAKE_DB[record_id].update(fields)
    return {"status": "updated", "record_id": record_id}


def delete(record_id: str):
    if record_id in _FAKE_DB:
        del _FAKE_DB[record_id]
        return {"status": "deleted", "record_id": record_id}
    return {"error": "not found"}


TOOL_REGISTRY = {"read": read, "write": write, "update": update, "delete": delete}
