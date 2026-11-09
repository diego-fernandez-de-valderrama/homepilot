from enum import StrEnum

from sqlalchemy import CheckConstraint


class EnumCheck:
    @staticmethod
    def one_of(column: str, values: type[StrEnum]) -> CheckConstraint:
        """The column may only hold the enum's values (e.g. "unknown stays unknown": no "Supported")."""
        allowed = ", ".join(f"'{value.value}'" for value in values)
        return CheckConstraint(f"{column} IN ({allowed})", name=column)
