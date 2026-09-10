"""add allowances table + debt_transactions.is_allowance

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "allowances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "kid_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kids.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column(
            "cadence",
            # values_callable so the DB enum labels are "weekly"/"monthly"
            # (the .value), not "WEEKLY"/"MONTHLY" — asyncpg rejects the
            # latter (see CLAUDE.md lessons learned).
            sa.Enum("weekly", "monthly", name="allowance_cadence"),
            nullable=False,
        ),
        sa.Column("payday", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # One allowance per kid — a regenerate updates the row in place.
    op.create_index("ix_allowances_kid_id", "allowances", ["kid_id"], unique=True)

    # server_default so every row written before this migration reads as
    # false rather than NULL (the is_savings/is_investment lesson in
    # CLAUDE.md — a new bool that new code treats as "always set").
    op.add_column(
        "debt_transactions",
        sa.Column("is_allowance", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("debt_transactions", "is_allowance")
    op.drop_table("allowances")
    sa.Enum(name="allowance_cadence").drop(op.get_bind())
