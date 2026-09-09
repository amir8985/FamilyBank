"""add savings_plans.preset_key

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Non-null only on a plan the parent switched on from a built-in
    # preset (see savings_service.PRESET_PLANS) — lets the settings UI
    # show that preset's toggle as on. NULL = a custom plan the parent
    # typed in themselves.
    op.add_column("savings_plans", sa.Column("preset_key", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("savings_plans", "preset_key")
