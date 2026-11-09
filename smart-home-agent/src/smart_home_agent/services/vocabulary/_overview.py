"""The canonical vocabulary as plain text, for the system instruction."""

from catalog_ingestion.vocabulary import CategoryVocabulary, CompatibilityVocabulary, Dimension, RequirementVocabulary

from smart_home_agent.services.vocabulary._owned_devices import NOT_OWNABLE


def vocabulary_overview() -> str:
    lines = ["Compatibility terms (canonical id: label):"]
    for dimension in (Dimension.ECOSYSTEM, Dimension.VOICE_ASSISTANT, Dimension.PROTOCOL, Dimension.MOBILE_OS):
        items = ", ".join(
            f"{t.canonical}: {t.label}" for t in CompatibilityVocabulary.TERMS if t.dimension is dimension
        )
        lines.append(f"- {dimension.value}: {items}")
    lines.append("Categories (key: English / German):")
    lines.extend(f"- {c.key}: {c.label_en} / {c.label_de}" for c in CategoryVocabulary.CATEGORIES)
    hubs = ", ".join(
        f"{t.canonical}: {t.label}"
        for t in RequirementVocabulary.TERMS
        if t.kind.value in ("hub", "gateway") and t.canonical not in NOT_OWNABLE
    )
    lines.append(f"Hubs and gateways a user may own: {hubs}")
    return "\n".join(lines)
