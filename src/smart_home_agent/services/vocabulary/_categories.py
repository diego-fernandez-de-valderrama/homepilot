"""Product categories: key, English/German label, URL slug or an everyday word -> canonical category key."""

from catalog_ingestion.vocabulary import CategoryVocabulary

from smart_home_agent.services.vocabulary._aliases import AMBIGUOUS_CATEGORIES, CATEGORY_SYNONYMS, key, singulars
from smart_home_agent.services.vocabulary.term_resolution_error import TermResolutionError


def resolve_category(value: str) -> str:
    for form in singulars(key(value)):
        if CategoryVocabulary.by_key(form.replace(" ", "_")):
            return form.replace(" ", "_")
        for category in CategoryVocabulary.CATEGORIES:
            if form in (key(category.label_en), key(category.label_de)) or form in category.slugs:
                return category.key
        if form in CATEGORY_SYNONYMS:
            return CATEGORY_SYNONYMS[form]
        if form in AMBIGUOUS_CATEGORIES:
            raise TermResolutionError("category", value, list(AMBIGUOUS_CATEGORIES[form]))
    raise TermResolutionError("category", value, [])
