from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Category(StrictModel):
    label: str | None = Field(max_length=120)
    value: float | None = Field(strict=True)
    evidence: str | None = Field(max_length=120, description="Visible numeric label, verbatim; null if unclear")

    @model_validator(mode="after")
    def require_evidence(self):
        if self.value is not None and not self.evidence:
            raise ValueError("Numeric values require visible label evidence")
        return self


class Extraction(StrictModel):
    supported: bool
    reason: str | None = Field(max_length=400)
    title: str | None = Field(max_length=200)
    unit: str | None = Field(max_length=80)
    categories: list[Category] = Field(max_length=12)
    warnings: list[str] = Field(max_length=12)

    @model_validator(mode="after")
    def check_scope(self):
        if self.supported and not 2 <= len(self.categories) <= 12:
            raise ValueError("Supported charts require 2–12 categories")
        if any(len(w) > 400 for w in self.warnings):
            raise ValueError("Warning too long")
        return self


class Draft(StrictModel):
    status: Literal["unreviewed"] = "unreviewed"
    source: Literal["gemini", "demo"]
    extraction: Extraction
    image_id: str | None = None
