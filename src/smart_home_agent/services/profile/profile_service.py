from smart_home_agent.models import (
    CustomerFact,
    CustomerProfile,
    CustomerSummary,
    FactKind,
    NewFact,
    ProfileUpdate,
    RejectedFact,
)
from smart_home_agent.repositories import ProfileStore
from smart_home_agent.services.profile._evidence_check import backed_by, check_quote
from smart_home_agent.services.profile._fact_builder import (
    OWNED_KINDS,
    device_fact,
    ecosystem_facts,
    hub_fact,
    language_fact,
    name_fact,
    preference_fact,
)
from smart_home_agent.services.profile._retraction import Retraction
from smart_home_agent.services.profile._text import clean, normalize
from smart_home_agent.services.profile._third_party import own_clauses


class ProfileService:
    def __init__(self, store: ProfileStore) -> None:
        self._store = store

    def profile(self, user_id: str, include_retracted: bool = False) -> CustomerProfile:
        return self._store.load(user_id, include_retracted)

    def customers(self) -> list[CustomerSummary]:
        return self._store.customers()

    def remember(
        self,
        user_id: str,
        session_id: str | None,
        user_message: str | None,
        evidence: str,
        *,
        name: str | None = None,
        language: str | None = None,
        ecosystems: list[str] | None = None,
        hubs: list[str] | None = None,
        owned_devices: list[str] | None = None,
        preferences: list[str] | None = None,
        no_longer_used: list[str] | None = None,
        no_longer_owned: list[str] | None = None,
    ) -> ProfileUpdate:
        """Checks the quote (raises `MemoryRuleError`), keeps only the values the customer stated, retracts what
        they no longer use or own, and stores the difference to the current profile."""
        quote = check_quote(user_message, evidence)
        current = self._store.load(user_id)

        # 1. Candidate facts from the arguments.
        rejected: list[RejectedFact] = []
        new: list[NewFact] = []
        if name is not None and name.strip():
            new.append(name_fact(name))
        if language is not None and language.strip():
            new += language_fact(language, rejected)
        new += ecosystem_facts(clean(ecosystems), rejected)
        new += [hub_fact(value) for value in clean(hubs)]
        new += [device_fact(value) for value in clean(owned_devices)]
        new += [preference_fact(value) for value in clean(preferences)]

        # 2. Only values stated in the customer's own words.
        own_words = "\n".join([normalize(quote), *own_clauses(normalize(user_message or ""))])
        unbacked = [fact for fact in new if not backed_by(fact, own_words)]
        rejected += [
            RejectedFact(kind=f.kind, value=f.label, reason="the evidence quote does not state it") for f in unbacked
        ]
        new = [fact for fact in new if fact not in unbacked]

        # 3. Retractions.
        retractions = [Retraction((FactKind.ECOSYSTEM,), v) for v in clean(no_longer_used)]
        retractions += [Retraction(OWNED_KINDS, v) for v in clean(no_longer_owned)]
        retract_ids, retract_rejected = Retraction.resolve(current, retractions)
        rejected += retract_rejected

        # 4. Difference to the stored profile; a single-valued kind supersedes its previous value.
        active = {(f.kind, f.value): f for f in current.active()}
        to_add: list[NewFact] = []
        unchanged: list[str] = []
        for fact in {(f.kind, f.value): f for f in new}.values():
            if (fact.kind, fact.value) in active and active[(fact.kind, fact.value)].id not in retract_ids:
                unchanged.append(fact.value)
                continue
            if fact.kind.is_single_valued:
                retract_ids += [f.id for f in current.active() if f.kind is fact.kind and f.id not in retract_ids]
            to_add.append(fact)

        added: list[CustomerFact] = []
        retracted: list[CustomerFact] = []
        if to_add or retract_ids:
            added, retracted = self._store.apply(user_id, session_id, quote, to_add, retract_ids)
        return ProfileUpdate(
            added=added,
            retracted=retracted,
            unchanged=unchanged,
            rejected=rejected,
            profile=self._store.load(user_id, include_retracted=True),
        )
