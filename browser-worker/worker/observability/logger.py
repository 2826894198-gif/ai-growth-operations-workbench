import logging
import re
import sys
from contextvars import ContextVar
from typing import Any, Dict, Optional

from pythonjsonlogger import jsonlogger

task_id_ctx: ContextVar[Optional[str]] = ContextVar("task_id", default=None)
profile_id_ctx: ContextVar[Optional[str]] = ContextVar("profile_id", default=None)
service_ctx: ContextVar[str] = ContextVar("service", default="browser-worker")

SENSITIVE_VALUE_RE = re.compile(
    r"(?i)(password|passwd|api[_\-]?key|secret|token|authorization|bearer|cookie|2fa|totp)"
    r"[\"']?\s*[:=]\s*[\"']?[^\s,;\"']+"
)
SENSITIVE_KEYS = re.compile(r"(password|passwd|api[_\-]?key|secret|token|authorization|cookie|2fa|totp)", re.IGNORECASE)


def redact(text: str) -> str:
    return SENSITIVE_VALUE_RE.sub(lambda m: m.group(0).split("=")[0] + "=***", text)


class WorkerJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = self.formatTime(record, self.datefmt)
        log_record["level"] = record.levelname
        log_record["service"] = service_ctx.get()
        log_record["task_id"] = task_id_ctx.get()
        log_record["profile_id"] = profile_id_ctx.get()
        for key in list(log_record.keys()):
            if SENSITIVE_KEYS.search(key):
                log_record[key] = "***"
        if "message" in log_record:
            log_record["message"] = redact(str(log_record["message"]))


def configure_logging(level: str = "INFO", service: str = "browser-worker") -> None:
    service_ctx.set(service)
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(WorkerJsonFormatter("%(message)s"))
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def set_log_context(task_id: Optional[str] = None, profile_id: Optional[str] = None) -> None:
    if task_id is not None:
        task_id_ctx.set(task_id)
    if profile_id is not None:
        profile_id_ctx.set(profile_id)
