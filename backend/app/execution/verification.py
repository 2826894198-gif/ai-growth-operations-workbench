"""Provider read-after-write verification with bounded retry (PART 06 §95-§98)."""

import asyncio
from typing import Any, Dict, List, Sequence


async def verify_with_retry(
    provider,
    intent,
    requested_state: Dict[str, Any],
    retry_seconds: Sequence[float] = (2, 5, 10),
) -> Dict[str, Any]:
    """Re-read provider state after mutation; bounded retries only."""
    attempts: List[Dict[str, Any]] = []
    for index, delay in enumerate(retry_seconds):
        try:
            verification = await provider.verify(intent, requested_state, requested_state)
            matched = bool(verification.get("matched"))
            provider_state = verification.get("provider_state") or {}
            attempts.append({"attempt": index + 1, "matched": matched, "state": provider_state, "verify": verification.get("result")})
            if matched:
                return {
                    "result": "MATCHED",
                    "attempts": attempts,
                    "provider_state": provider_state,
                    "matched": True,
                }
        except Exception as exc:  # noqa: BLE001
            attempts.append({"attempt": index + 1, "matched": False, "error": str(exc)})
        if index < len(retry_seconds) - 1 and delay > 0:
            await asyncio.sleep(delay)
    last_state = attempts[-1].get("state") if attempts else None
    return {
        "result": "MISMATCHED" if last_state is not None else "UNAVAILABLE",
        "attempts": attempts,
        "provider_state": last_state,
        "matched": False,
    }
