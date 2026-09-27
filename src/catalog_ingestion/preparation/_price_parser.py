import re
from decimal import Decimal
from typing import ClassVar

from catalog_ingestion.models import Price


class PriceParser:
    """Price parsing for the German retail formats found in the dataset.

    Observed formats: `124,95 €`, `999,- €`, `9.999,- €` and one discounted, multi-line
    form: `Ersparnis: 20,- €\\nStatt 159,95\\n139,95 €`.
    """

    _AMOUNT = re.compile(r"(?P<int>\d{1,3}(?:\.\d{3})+|\d+)(?:,(?P<dec>\d{1,2}|-))?")
    _CURRENCIES: ClassVar[dict[str, str]] = {"€": "EUR", "EUR": "EUR"}

    @staticmethod
    def parse(raw: str) -> Price:
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        current: Decimal | None = None
        original: Decimal | None = None
        savings: Decimal | None = None
        currency: str | None = None
        for line in lines:
            lowered = line.casefold()
            if lowered.startswith("ersparnis"):
                savings = PriceParser.parse_amount(line)
            elif lowered.startswith("statt"):
                original = PriceParser.parse_amount(line)
            else:
                current = PriceParser.parse_amount(line)
                currency = PriceParser._currency(line) or currency
        if currency is None and current is not None:
            currency = PriceParser._currency(raw)
        return Price(value=current, currency=currency, original_value=original, savings=savings, raw=raw)

    @staticmethod
    def parse_amount(text: str) -> Decimal | None:
        match = PriceParser._AMOUNT.search(text)
        if match is None:
            return None
        integer = match.group("int").replace(".", "")
        decimals = match.group("dec")
        if decimals is None or decimals == "-":
            return Decimal(integer).quantize(Decimal("0.01"))
        return Decimal(f"{integer}.{decimals.ljust(2, '0')}")

    @staticmethod
    def _currency(text: str) -> str | None:
        return next((code for symbol, code in PriceParser._CURRENCIES.items() if symbol in text), None)
