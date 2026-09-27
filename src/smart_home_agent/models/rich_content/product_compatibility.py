from pydantic import BaseModel

from smart_home_agent.models.compatibility import CompatibilityResult


class ProductCompatibility(BaseModel):
    result: CompatibilityResult
    against_setup: bool  # True: checked against the customer's stated setup; False: the product's own facts
