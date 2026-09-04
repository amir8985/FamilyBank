"""add consent_accepted_at to users

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: existing users signed up before the consent-gated flow
    # existed, so there's nothing honest to backfill here. NULL means
    # "predates this feature", not "declined."
    op.add_column(
        "users",
        sa.Column("consent_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "consent_accepted_at")
