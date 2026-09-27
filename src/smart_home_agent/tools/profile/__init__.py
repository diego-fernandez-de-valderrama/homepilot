"""Lasting customer memory (`remember_customer_facts`): facts the customer stated about themself, stored across
conversations. The rules (verbatim evidence, no facts about other people) live in `ProfileService`."""

from smart_home_agent.tools.profile.remember_customer_facts_tool import RememberCustomerFactsTool

__all__ = ["RememberCustomerFactsTool"]
