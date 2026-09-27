"""Hub facts.

Bridges, hubs, gateways and connectors get their own fact kind `hub`. Owned devices that were stored with a
specific canonical hub id move to it.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-27 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The specific hub and gateway ids of catalog_ingestion/vocabulary/_requirement_terms.py at this revision (a
# migration must not change with the vocabulary).
_HUB_IDS = (
    "bosch_smart_home_controller",
    "homematic_ip_access_point",
    "homematic_ccu3",
    "third_party_partner_solution",
    "philips_hue_bridge",
    "ring_alarm_base_station",
    "gardena_smart_gateway",
    "essentials_smart_home_hub",
)


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("UPDATE customer_facts SET kind = 'hub' WHERE kind = 'owned_device' AND canonical IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": list(_HUB_IDS)},
    )


def downgrade() -> None:
    # An active hub that is also stored as an active owned device (same value) is a duplicate: drop it.
    op.execute(
        """
        DELETE FROM customer_facts h
        WHERE h.kind = 'hub' AND h.active AND EXISTS (
            SELECT 1 FROM customer_facts o
            WHERE o.user_id = h.user_id AND o.kind = 'owned_device' AND o.value = h.value AND o.active
        )
        """
    )
    op.execute("UPDATE customer_facts SET kind = 'owned_device' WHERE kind = 'hub'")
