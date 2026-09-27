from dataclasses import dataclass

from smart_home_agent.models import CustomerProfile, FactKind, RejectedFact
from smart_home_agent.services.profile._text import normalize
from smart_home_agent.services.vocabulary import TermResolutionError, Vocabulary


@dataclass(frozen=True, slots=True)
class Retraction:
    """A value the customer no longer uses or owns, matched against stored facts of `kinds`."""

    kinds: tuple[FactKind, ...]
    text: str

    @staticmethod
    def resolve(current: CustomerProfile, retractions: list["Retraction"]) -> tuple[list[int], list[RejectedFact]]:
        """(ids of the stored facts to retract, retractions that match no stored fact)."""
        ids: list[int] = []
        rejected: list[RejectedFact] = []
        for item in retractions:
            candidates = item._values()
            matches = [
                f
                for f in current.active()
                if f.kind in item.kinds and (f.value in candidates or normalize(f.label) in candidates)
            ]
            if not matches:
                rejected.append(RejectedFact(kind=item.kinds[0], value=item.text, reason="not in the stored profile"))
            ids += [f.id for f in matches if f.id not in ids]
        return ids, rejected

    def _values(self) -> set[str]:
        values = {normalize(self.text)}
        try:
            if FactKind.ECOSYSTEM in self.kinds:
                values.add(Vocabulary.resolve_term(self.text).canonical)
            else:
                values.add(Vocabulary.resolve_owned_device(self.text))
        except TermResolutionError:
            pass  # match on the customer's wording only
        return values
