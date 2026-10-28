import base64
import hashlib
import hmac as hmac_module


def compute_hmac(raw_body: bytes, secret: str) -> str:
    digest = hmac_module.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def verify_webhook(raw_body: bytes, secret: str, signature: str) -> bool:
    if not secret or not signature:
        return False
    expected = compute_hmac(raw_body, secret)
    return hmac_module.compare_digest(expected, signature)
