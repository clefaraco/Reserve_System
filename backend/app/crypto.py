import base64
import hashlib
import hmac
import json
import os
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import settings


def encrypt(value: dict, aad: str) -> bytes:
    nonce = os.urandom(12)
    key = base64.b64decode(settings().pii_key_base64)
    return nonce + AESGCM(key).encrypt(
        nonce, json.dumps(value, ensure_ascii=False).encode(), aad.encode()
    )


def decrypt(value: bytes, key_id: str, aad: str) -> dict:
    if key_id != settings().pii_key_id:
        raise ValueError("Unknown encryption key version; restore the configured KMS keyring")
    key = base64.b64decode(settings().pii_key_base64)
    return json.loads(AESGCM(key).decrypt(value[:12], value[12:], aad.encode()))


def keyed_hash(value: str, domain: str) -> bytes:
    key = base64.b64decode(settings().email_hmac_key_base64)
    return hmac.digest(key, f"{domain}:{value}".encode(), hashlib.sha256)


def email_index(tenant_id: UUID, email: str) -> bytes:
    # Match the Auth provider's email normalization; don't collapse dots or plus tags.
    return keyed_hash(email.strip().lower(), f"email:{tenant_id}")
