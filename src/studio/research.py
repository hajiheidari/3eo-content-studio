"""Provider boundary. No network call or synthetic source analysis by default."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .domain import WEIGHTS


class Research(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title_fa: str = Field(min_length=1, max_length=300)
    summary_fa: str = Field(min_length=1, max_length=10000)
    angle_fa: str = Field(min_length=1, max_length=2000)
    why_it_matters_fa: str = Field(default="نیازمند تکمیل پژوهش", max_length=2000)
    recommended_format_fa: str = Field(default="نیازمند انتخاب قالب", max_length=300)
    brand_connection_fa: str = Field(default="ارتباط با ابزارهای 3EO مشخص نشده", max_length=2000)
    claims_to_verify: list[str]
    limitations: list[str] = Field(min_length=1)
    criteria: dict[str, float]

    @field_validator(
        "title_fa", "summary_fa", "angle_fa", "why_it_matters_fa",
        "recommended_format_fa", "brand_connection_fa",
    )
    @classmethod
    def persian(cls, value):
        if not any("\u0600" <= c <= "\u06ff" for c in value):
            raise ValueError("Persian text required")
        return value

    @field_validator("criteria")
    @classmethod
    def scores(cls, value):
        if set(value) != set(WEIGHTS) or any(not 0 <= n <= 100 for n in value.values()):
            raise ValueError("Invalid ranking criteria")
        return value


class ResearchProvider(Protocol):
    def analyze(self, transcript: str, source_url: str) -> Research: ...


class UnconfiguredProvider:
    def analyze(self, transcript: str, source_url: str) -> Research:
        raise RuntimeError("No research provider configured; submit reviewed research manually")
