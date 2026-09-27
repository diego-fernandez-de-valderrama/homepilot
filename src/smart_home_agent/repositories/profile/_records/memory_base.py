from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import MetaData, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import DeclarativeBase


class MemoryBase(DeclarativeBase):
    """Declarative base of the customer memory database (its metadata is what Alembic autogenerates from)."""

    # Matches PostgreSQL's default constraint names, so names are predictable in migrations.
    NAMING_CONVENTION: ClassVar[dict[str, str]] = {
        "ix": "%(table_name)s_%(column_0_name)s_idx",
        "uq": "%(table_name)s_%(column_0_name)s_key",
        "ck": "%(table_name)s_%(constraint_name)s_check",
        "fk": "%(table_name)s_%(column_0_name)s_fkey",
        "pk": "%(table_name)s_pkey",
    }

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {str: Text, datetime: TIMESTAMP(timezone=True)}
