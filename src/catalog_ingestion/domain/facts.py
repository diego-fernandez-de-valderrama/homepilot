"""Compatibility facts and requirements with provenance."""

from dataclasses import dataclass

from catalog_ingestion.domain.enums import (
    Dimension,
    FactSource,
    FactStatus,
    Method,
    Necessity,
    RequirementKind,
)


@dataclass(frozen=True, slots=True)
class Evidence:
    source: FactSource
    text: str
    field: str | None = None  # e.g. "attributes.Unterstützte Systeme", "title", "description"
    url: str | None = None  # set for web evidence


@dataclass(frozen=True, slots=True)
class CompatibilityFact:
    dimension: Dimension
    raw_value: str
    canonical_value: str | None  # None when the raw value has no safe canonical mapping
    status: FactStatus
    evidence: Evidence
    confidence: float
    method: Method

    @property
    def key(self) -> tuple[Dimension, str]:
        return self.dimension, self.canonical_value or self.raw_value.casefold()


@dataclass(frozen=True, slots=True)
class Requirement:
    item: str
    canonical_item: str | None
    kind: RequirementKind
    necessity: Necessity
    alternatives: tuple[str, ...]  # canonical ids; any one of them satisfies the requirement
    evidence: Evidence
    confidence: float
    method: Method

    @property
    def key(self) -> str:
        return self.canonical_item or self.item.casefold()
