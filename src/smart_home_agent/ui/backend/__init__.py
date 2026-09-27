"""Everything the UI reads from outside Streamlit: cached per process, and failures never break the page.

- `AgentBackend`: the agent service (built on the first message), the turn starters (`TurnStarter`), the live
  cart, quantity edits and which cart confirmations already ran;
- `CustomerDirectory`: the customer memory for the testing controls, usable before the agent exists;
- `ImageAvailability`: which product image URLs are gone, so cards use their text-only layout instead.
"""

from smart_home_agent.ui.backend.agent_backend import AgentBackend
from smart_home_agent.ui.backend.customer_directory import CustomerDirectory
from smart_home_agent.ui.backend.image_availability import ImageAvailability
from smart_home_agent.ui.backend.turn_starter import TurnStarter

__all__ = ["AgentBackend", "CustomerDirectory", "ImageAvailability", "TurnStarter"]
