"""Optional OpenTelemetry bootstrap (PART 07 §156-§160).

No-op unless OTEL_ENABLED=true and the SDK is installed; observability never
becomes a request dependency.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def init_telemetry(service_name: str = "growth-backend") -> None:
    if not settings.otel_enabled:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": service_name, "environment": settings.app_env}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_endpoint or None)))
        trace.set_tracer_provider(provider)
        logger.info("OpenTelemetry initialized", extra={"event": "otel_started", "endpoint": settings.otel_endpoint})
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenTelemetry unavailable; continuing without tracing", extra={"event": "otel_disabled", "error": str(exc)})
