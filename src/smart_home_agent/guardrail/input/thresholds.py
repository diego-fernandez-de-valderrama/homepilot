"""Settings of the decision rule: minimum similarity per category and minimum distance to the runner-up."""

from pydantic import BaseModel, Field

from smart_home_agent.guardrail.input.category import BLOCKING, Category


class GuardrailThresholds(BaseModel):
    """Minimum similarity per category and minimum distance to the runner-up category.

    Below the threshold, or closer than `margin` to the second category, the decision is UNCERTAIN
    and the message goes to the agent: an ambiguous message is never blocked.

    OFF_TOPIC needs more evidence than the other blocking categories. Short, content-free messages
    ("hmm", "I'm Diego") score about 0.77-0.84 against every category, right where off-topic requests
    start, and a missed off-topic message is cheap (the agent's prompt still redirects it) while a
    wrongly blocked small-talk message breaks the conversation.
    """

    smart_home: float = Field(ge=0.0, le=1.0)
    electrical: float = Field(ge=0.0, le=1.0)
    off_topic: float = Field(ge=0.0, le=1.0)
    prompt_injection: float = Field(ge=0.0, le=1.0)
    margin: float = Field(ge=0.0, le=1.0)
    off_topic_margin: float = Field(default=0.0, ge=0.0, le=1.0)  # effective margin: max(margin, this)
    off_topic_min_words: int = Field(default=0, ge=0)  # shorter messages are never OFF_TOPIC
    # OFF_TOPIC is still classified (for the output check and the developer panel) but only blocks when true.
    block_off_topic: bool = False

    def for_category(self, category: Category) -> float:
        return getattr(self, category.value.lower())

    def margin_for(self, category: Category) -> float:
        return max(self.margin, self.off_topic_margin) if category is Category.OFF_TOPIC else self.margin

    def blocked_categories(self) -> frozenset[Category]:
        """Categories that are blocked at input with these settings (off-topic only when enabled)."""
        return BLOCKING if self.block_off_topic else BLOCKING - {Category.OFF_TOPIC}
