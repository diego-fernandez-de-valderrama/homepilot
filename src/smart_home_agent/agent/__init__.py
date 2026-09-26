"""ADK agent layer.

google-adk 2.x builds tool declarations with its JSON-schema feature, which is enabled by default but
still flagged EXPERIMENTAL, so every process prints a UserWarning once. The tools are verified to work
with it (see tests/unit/test_tools.py), so only that exact warning is silenced; all other warnings stay.
"""

import warnings

warnings.filterwarnings(
    "ignore",
    message=r"\[EXPERIMENTAL\] feature FeatureName\.JSON_SCHEMA_FOR_FUNC_DECL is enabled",
    category=UserWarning,
)
