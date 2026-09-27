from decimal import Decimal


class NumberConversion:
    """Decimal (domain, PostgreSQL) <-> float (JSON schemas)."""

    @staticmethod
    def to_float(value: Decimal | None) -> float | None:
        return float(value) if value is not None else None

    @staticmethod
    def to_decimal(value: float | None) -> Decimal | None:
        return Decimal(str(value)).quantize(Decimal("0.01")) if value is not None else None
