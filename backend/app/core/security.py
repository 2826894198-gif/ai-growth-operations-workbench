import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


def _fernet() -> Fernet:
    key = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.warning("failed to decrypt secret", extra={"event": "decrypt_failed"})
        return ""


def redact_secrets(value: str) -> str:
    """Best-effort redaction for values that may contain key=secret pairs."""
    import re

    pattern = re.compile(
        r"(?i)(password|passwd|api[_\-]?key|secret|token|authorization|bearer|cookie)"
        r"[\"']?\s*[:=]\s*[\"']?[^\s,;\"']+"
    )
    return pattern.sub(lambda m: m.group(0).split("=")[0] + "=***", value)


def require_worker_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> None:
    if not settings.worker_token:
        return
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Worker authentication required")
    if credentials.credentials != settings.worker_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid worker token")
