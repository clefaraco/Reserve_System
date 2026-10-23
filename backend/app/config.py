import base64
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore", hide_input_in_errors=True)

    database_url: str = Field(repr=False)
    pii_key_id: str = "local-v1"
    pii_key_base64: str = Field(repr=False)
    email_hmac_key_base64: str = Field(repr=False)
    vault_signing_key_base64: str = Field(repr=False)
    cors_origins: list[str] = ["http://localhost:5173"]
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    auth_audience: str = "authenticated"
    vault_bucket: str = ""
    vault_region: str = "us-east-1"
    vault_kms_key_id: str = ""
    staff_email_send_enabled: bool = False
    resend_api_key: str = Field(default="", repr=False)
    resend_webhook_secret: str = Field(default="", repr=False)
    staff_email_from: str = ""
    staff_accept_url: str = ""
    notification_webhook_url: str = ""
    notification_webhook_token: str = Field(default="", repr=False)

    @field_validator("pii_key_base64", "email_hmac_key_base64", "vault_signing_key_base64")
    @classmethod
    def strong_key(cls, value: str) -> str:
        if len(base64.b64decode(value, validate=True)) != 32:
            raise ValueError("Expected a base64-encoded, random 32-byte key")
        return value

    @field_validator("supabase_url", "notification_webhook_url", "staff_accept_url")
    @classmethod
    def https_only(cls, value: str) -> str:
        if value and not value.startswith("https://"):
            raise ValueError("External services require HTTPS")
        return value.rstrip("/")

    @field_validator("staff_accept_url")
    @classmethod
    def accept_url_is_fixed(cls, value: str) -> str:
        from urllib.parse import urlsplit

        if value:
            parts = urlsplit(value)
            if (
                not parts.hostname
                or parts.username
                or parts.password
                or parts.query
                or parts.fragment
            ):
                raise ValueError("Invitation redirect must be a fixed HTTPS URL")
        return value

    @property
    def auth_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_publishable_key)


@lru_cache
def settings() -> Settings:
    return Settings()
