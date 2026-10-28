"""Secret provider interface (PART 07 §37-§39).

Business code only uses credential_reference; providers resolve the actual
secret from env / secret manager. Raw secrets never leave this module.
"""

import os
from typing import Optional, Protocol

from app.core.config import settings


class SecretProvider(Protocol):
    def get(self, reference: str) -> Optional[str]: ...


class LocalEnvSecretProvider:
    """Development/local provider. Staging/production should use a real secret
    manager; the interface keeps business code unchanged."""

    def get(self, reference: str) -> Optional[str]:
        if not reference:
            return None
        if reference.startswith("env:"):
            return os.environ.get(reference[4:], None)
        if reference.startswith("enc://"):
            return os.environ.get(reference[6:].upper(), None)
        return os.environ.get(reference, None)


def get_secret_provider() -> SecretProvider:
    if settings.app_env in ("staging", "production") and os.environ.get("SECRET_PROVIDER", "local") != "local":
        try:
            from app.core.vault_provider import VaultSecretProvider

            return VaultSecretProvider()
        except ImportError:
            pass
    return LocalEnvSecretProvider()


def resolve_secret(reference: str) -> Optional[str]:
    return get_secret_provider().get(reference)
