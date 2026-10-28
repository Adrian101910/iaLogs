import json
import math
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, StringConstraints, field_validator

ShortText = Annotated[str, StringConstraints(min_length=1, max_length=4000)]
Severity = Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def normalize_severity(value: str) -> str:
    value = value.strip().upper()
    return {"WARN": "WARNING", "FATAL": "CRITICAL", "ERR": "ERROR", "INFORMATION": "INFO"}.get(value, value)


def validate_json(value, depth=0):
    if depth > 20:
        raise ValueError("Los atributos JSON superan 20 niveles")
    if isinstance(value, str):
        validate_text(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("JSON requiere números finitos")
    if isinstance(value, dict):
        for key, child in value.items():
            validate_text(key)
            validate_json(child, depth + 1)
    if isinstance(value, list):
        for child in value:
            validate_json(child, depth + 1)


def validate_text(value: str):
    if "\x00" in value:
        raise ValueError("El texto no admite caracteres NUL")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError("El texto debe ser Unicode válido") from None


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LogInput(StrictModel):
    timestamp: AwareDatetime
    source: str = Field(min_length=1, max_length=255)
    service: str | None = Field(default=None, min_length=1, max_length=255)
    severity: Severity
    message: str = Field(min_length=1, max_length=65_536)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def utc_timestamp(cls, value):
        return value.astimezone(timezone.utc)

    @field_validator("severity", mode="before")
    @classmethod
    def severity_alias(cls, value):
        return normalize_severity(value) if isinstance(value, str) else value

    @field_validator("source", "service", "message")
    @classmethod
    def postgres_text(cls, value):
        if value is not None:
            validate_text(value)
            if not value.strip():
                raise ValueError("El texto no puede estar vacío")
        return value

    @field_validator("attributes")
    @classmethod
    def bounded_attributes(cls, value):
        validate_json(value)
        if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 65_536:
            raise ValueError("Los atributos superan 65536 bytes")
        return value


class LogBatch(StrictModel):
    events: list[LogInput] = Field(min_length=1, max_length=5000)


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    timestamp: datetime
    received_at: datetime
    source: str
    service: str | None
    severity: Severity
    message: str
    attributes: dict[str, JsonValue]


class LogPage(BaseModel):
    items: list[LogOut]
    total: int
    limit: int | None = None
    offset: int | None = None


class AnalysisInput(StrictModel):
    log_ids: list[UUID] = Field(min_length=1, max_length=100)

    @field_validator("log_ids")
    @classmethod
    def distinct_ids(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Los IDs deben ser únicos")
        return value


class Finding(StrictModel):
    description: ShortText
    log_ids: list[UUID] = Field(min_length=1, max_length=100)


class Evidence(StrictModel):
    log_id: UUID
    explanation: ShortText


class Diagnosis(StrictModel):
    summary: ShortText
    findings: list[Finding] = Field(max_length=30)
    possible_causes: list[Finding] = Field(max_length=20)
    evidence: list[Evidence] = Field(min_length=1, max_length=100)
    next_checks: list[ShortText] = Field(max_length=20)
    missing_information: list[ShortText] = Field(max_length=20)
    uncertainty: Literal["low", "medium", "high"]


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    model: str
    prompt_version: str
    log_ids: list[UUID]
    diagnosis: Diagnosis


class AnalysisPage(BaseModel):
    items: list[AnalysisOut]
    total: int
    limit: int
    offset: int
