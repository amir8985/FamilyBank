"""add savings_plans, savings_deposits, debt_transactions.is_savings

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "savings_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "family_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("families.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("monthly_rate", sa.Numeric(6, 3), nullable=False),
        sa.Column("lock_months", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_savings_plans_family_id", "savings_plans", ["family_id"])

    op.create_table(
        "savings_deposits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "kid_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kids.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("savings_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("plan_name", sa.String(), nullable=False),
        sa.Column("monthly_rate", sa.Numeric(6, 3), nullable=False),
        sa.Column("lock_months", sa.Integer(), nullable=False),
        sa.Column("principal", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("matures_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("close_currency", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_savings_deposits_kid_id", "savings_deposits", ["kid_id"])
    op.create_index("ix_savings_deposits_is_open", "savings_deposits", ["is_open"])

    # server_default so every row written before this migration reads as
    # false rather than NULL (the is_investment/is_adjustment lesson in
    # CLAUDE.md — a new bool that new code treats as "always set").
    op.add_column(
        "debt_transactions",
        sa.Column("is_savings", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("debt_transactions", "is_savings")
    op.drop_table("savings_deposits")
    op.drop_table("savings_plans")
