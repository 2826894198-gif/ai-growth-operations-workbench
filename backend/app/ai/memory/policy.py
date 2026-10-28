import re

FORBIDDEN_PATTERNS = re.compile(
    r"(?i)(password|api[_-]?key|access[_-]?token|secret|private[_-]?key|2fa|totp|email|phone|address)"
)


def memory_write_allowed(statement: str, evidence_refs: list, status: str = "PROPOSED") -> tuple:
    if FORBIDDEN_PATTERNS.search(statement):
        return False, "FORBIDDEN_CONTENT"
    if status == "VERIFIED" and not evidence_refs:
        return False, "VERIFIED_REQUIRES_EVIDENCE"
    if len(statement) > 2000:
        return False, "TOO_LONG"
    return True, None
