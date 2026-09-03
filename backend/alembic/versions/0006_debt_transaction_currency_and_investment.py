"""add from/to currency and is_investment to debt_transactions

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("debt_transactions", sa.Column("from_currency", sa.String(), nullable=True))
    op.add_column("debt_transactions", sa.Column("to_currency", sa.String(), nullable=True))
    op.add_column(
        "debt_transactions",
        sa.Column("is_investment", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("debt_transactions", "is_investment")
    op.drop_column("debt_transactions", "to_currency")
    op.drop_column("debt_transactions", "from_currency")
