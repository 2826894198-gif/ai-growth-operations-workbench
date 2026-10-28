"""Google Ads API v25 write error mapping (PART 06 §155-§156)."""

from app.execution.errors import ExecutionError, ExecutionErrorCode


def map_google_write_error(exc: Exception, request_id: str = None) -> ExecutionError:
    message = str(exc)
    text = message.lower()
    if "timeout" in text or "deadline" in text:
        return ExecutionError(
            ExecutionErrorCode.PROVIDER_TIMEOUT.value,
            message,
            provider_error_code="TIMEOUT",
            provider_request_id=request_id,
        )
    if "rate" in text or "quota" in text:
        return ExecutionError(
            ExecutionErrorCode.PROVIDER_MUTATION_FAILED.value,
            message,
            provider_error_code="RATE_LIMITED",
            provider_request_id=request_id,
        )
    if "authentication" in text or "authorization" in text or "permission" in text:
        return ExecutionError(
            ExecutionErrorCode.PROVIDER_MUTATION_FAILED.value,
            message,
            provider_error_code="AUTH_ERROR",
            provider_request_id=request_id,
        )
    return ExecutionError(
        ExecutionErrorCode.PROVIDER_MUTATION_FAILED.value,
        message,
        provider_error_code="GOOGLE_ADS_ERROR",
        provider_request_id=request_id,
    )
