"""Meta Marketing API v26 write error mapping (PART 06 §155-§156)."""

from typing import Any, Dict

from app.execution.errors import ExecutionError, ExecutionErrorCode


def map_meta_write_error(error: Dict[str, Any], request_id: str = None) -> ExecutionError:
    code = error.get("code")
    message = error.get("message", "meta mutation failed")
    error_subcode = error.get("error_subcode")
    if code in (4, 17, 341, 613) or error_subcode in (2446079, 1487332):
        return ExecutionError(
            ExecutionErrorCode.PROVIDER_MUTATION_FAILED.value,
            message,
            provider_error_code=str(error_subcode or code),
            provider_request_id=request_id,
        )
    if code in (1, 2, 10, 190, 200):
        return ExecutionError(
            ExecutionErrorCode.PROVIDER_MUTATION_FAILED.value,
            f"meta auth/permission error: {message}",
            provider_error_code=str(error_subcode or code),
            provider_request_id=request_id,
        )
    return ExecutionError(
        ExecutionErrorCode.PROVIDER_MUTATION_FAILED.value,
        message,
        provider_error_code=str(error_subcode or code),
        provider_request_id=request_id,
    )
