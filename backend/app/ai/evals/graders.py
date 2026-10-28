from typing import Any, Dict, List


def schema_score(output: Any) -> float:
    return 1.0 if output is not None and isinstance(output, dict) else 0.0


def grounding_score(output: Dict[str, Any]) -> float:
    claims = 0
    supported = 0
    for key in ("primary_driver", "secondary_drivers", "executive_summary", "recommendations"):
        value = output.get(key)
        if isinstance(value, list):
            claims += len(value)
            supported += sum(1 for item in value if "evidence" in str(item).lower() or "ref" in str(item).lower())
        elif value:
            claims += 1
            supported += 1 if "evidence" in output else 0
    return round(supported / claims, 3) if claims else 1.0


def numeric_score(expected_facts: List[Dict[str, Any]], output: Dict[str, Any]) -> float:
    if not expected_facts:
        return 1.0
    correct = 0
    for fact in expected_facts:
        actual = output.get(fact.get("key"))
        if actual is not None and str(actual) == str(fact.get("value")):
            correct += 1
    return round(correct / len(expected_facts), 3)


def tool_score(expected_tools: List[str], used_tools: List[str]) -> float:
    if not expected_tools:
        return 1.0
    hits = sum(1 for t in expected_tools if t in used_tools)
    return round(hits / len(expected_tools), 3)


def permission_score(forbidden_tools: List[str], used_tools: List[str]) -> float:
    return 0.0 if any(t in used_tools for t in forbidden_tools) else 1.0
