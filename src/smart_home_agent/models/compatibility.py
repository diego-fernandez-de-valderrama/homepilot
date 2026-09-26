"""Compatibility check results. `unknown` is a real state, never a default for supported/unsupported."""

from typing import Literal

from catalog_ingestion.domain.enums import Dimension, FactStatus, Necessity, RequirementKind
from pydantic import BaseModel

from smart_home_agent.models.evidence import Evidence

RequirementStatus = Literal["satisfied", "missing", "unverified", "info"]


class TermCheck(BaseModel):
    term: str  # canonical id
    label: str
    dimension: Dimension
    status: FactStatus
    evidence: list[Evidence]
    notes: list[str]


class RequirementCheck(BaseModel):
    label: str
    canonical_item: str | None
    kind: RequirementKind
    necessity: Necessity
    alternatives: list[str]  # human-readable labels
    status: RequirementStatus
    evidence: Evidence


class CompatibilityResult(BaseModel):
    product_id: str
    title: str
    overall: FactStatus
    checks: list[TermCheck]
    requirements: list[RequirementCheck]
    requires_professional_installation: bool
