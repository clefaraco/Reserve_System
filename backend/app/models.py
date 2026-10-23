from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Guest(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, pattern=r"^\+[1-9]\d{7,14}$")


class Booking(StrictModel):
    service_id: UUID
    resource_id: UUID
    starts_at: AwareDatetime
    patient: Guest
    consent_document_ids: list[UUID] = Field(min_length=2, max_length=3)
    create_account: bool = False
    whatsapp: bool = False

    @field_validator("starts_at")
    @classmethod
    def normalize_time(cls, value: datetime):
        return value.astimezone(UTC)


class ChangeAppointment(StrictModel):
    action: Literal["confirm", "cancel", "reschedule"]
    starts_at: AwareDatetime | None = None
    expected_version: int = Field(ge=1)


class PrivacyRequest(StrictModel):
    patient_id: UUID
    kind: Literal["anonymize", "rectify", "oppose", "withdraw_consent"]
