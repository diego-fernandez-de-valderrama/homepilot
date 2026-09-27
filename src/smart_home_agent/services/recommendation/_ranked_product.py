from smart_home_agent.models import CompatibilityResult, RankedProduct, VersionOption
from smart_home_agent.services.recommendation.ranking_candidate import RankingCandidate
from smart_home_agent.services.vocabulary import Vocabulary


def to_ranked_product(
    candidate: RankingCandidate, result: CompatibilityResult, other_versions: list[VersionOption]
) -> RankedProduct:
    return RankedProduct(
        product=candidate.product.summary(),
        compatibility=result.overall,
        checks=result.checks,
        relevance=round(candidate.relevance, 4),
        score=candidate.score,
        capabilities=sorted(Vocabulary.label(c) for c in candidate.capabilities),
        missing_requirements=[r.label for r in result.requirements if r.status == "missing"],
        unverified_requirements=[r.label for r in result.requirements if r.status == "unverified"],
        requires_professional_installation=result.requires_professional_installation,
        other_versions=other_versions,
    )
