"""ADK agent layer.

google-adk 2.x flags two features this agent relies on as EXPERIMENTAL and prints a UserWarning once per
process for each: the JSON-schema tool declarations (enabled by default) and tool confirmation (the cart
tools). Both are verified by tests (tests/unit/test_tools.py, tests/unit/test_cart_agent.py), so only those
exact warnings are silenced; all other warnings stay.
"""

import warnings

warnings.filterwarnings(
    "ignore",
    message=r"\[EXPERIMENTAL\] feature FeatureName\.(JSON_SCHEMA_FOR_FUNC_DECL|TOOL_CONFIRMATION) is enabled",
    category=UserWarning,
)
