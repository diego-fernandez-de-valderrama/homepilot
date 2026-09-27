"""Regular expressions for the tag grammar (see the package docstring)."""

import re

ID = r"\d{8}"
IDS = rf"{ID}(?:\s*,\s*{ID})*"
ITEM = re.compile(rf'<item\s+id="({ID})"\s*/>')
BLOCK = re.compile(
    rf'<(?P<list>items|compare)\s+ids="(?P<ids>{IDS})"\s*/>'
    rf'|<compatibility\s+id="(?P<compat>{ID})"\s*/>'
    rf'|<upgrade\s+from="(?P<from>{ID})"\s+to="(?P<to>{ID})"\s*/>'
    rf'|<upgrade\s+to="(?P<to_first>{ID})"\s+from="(?P<from_second>{ID})"\s*/>'  # attribute order is free
)
FENCE = re.compile(r"(```.*?(?:```|\Z))", re.DOTALL)  # capturing: re.split keeps the fences
# Anything that looks like one of the tags (opening, closing, self-closing, or cut off at the line end).
TAG_LIKE = re.compile(r"</?\s*(?:items?|compare|compatibility|upgrade)\b[^<>\n]*(?:>|$)", re.IGNORECASE | re.MULTILINE)
# A tag the model broke over several lines (`<items ids="1,\n2"/>`): joined into one line before parsing.
SPLIT_TAG = re.compile(r"<\s*(?:items?|compare|compatibility|upgrade)\b[^<>]{0,300}>", re.IGNORECASE)
COMPARE_SIZES = range(2, 5)  # services.comparison.MIN_PRODUCTS..MAX_PRODUCTS
