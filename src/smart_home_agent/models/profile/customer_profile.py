from pydantic import BaseModel, Field

from smart_home_agent.models.profile._prompt_value import PromptValue
from smart_home_agent.models.profile.customer_fact import CustomerFact


class CustomerProfile(BaseModel):
    user_id: str
    facts: list[CustomerFact] = Field(default_factory=list)

    def active(self) -> list[CustomerFact]:
        return [f for f in self.facts if f.active]

    def prompt_lines(self) -> list[str]:
        """Facts for the system instruction: active ones with the customer's wording, then what the customer no
        longer owns or uses. Evidence quotes are left out on purpose: a quote can mention a fact that was
        retracted later ("I use HomeKit and have a Hue Bridge"), and the model would read it as current."""
        active = self.active()
        lines = [
            f"- {f.kind.value}: {PromptValue.inline(f.value)}"
            + (f' ("{PromptValue.inline(f.label)}")' if f.label.casefold() != f.value.casefold() else "")
            for f in active
        ]
        current = {(f.kind, f.value) for f in active}
        gone = dict.fromkeys(
            (f.kind, f.value)
            for f in self.facts
            if not f.active and PromptValue.no_longer(f.kind) and (f.kind, f.value) not in current
        )
        lines += [
            f"- {PromptValue.no_longer(kind)}: {PromptValue.inline(value)} (the customer said so: do not assume it)"
            for kind, value in gone
        ]
        return lines
