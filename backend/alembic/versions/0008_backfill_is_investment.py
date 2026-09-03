"""backfill is_investment on pre-existing buy/sell debt rows

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-03

Same gap as 0007, for the other new column migration 0006 added:
is_investment defaults to false, so every debt row buy()/sell() wrote
before today reads as a generic manual add/deduct instead of "Bought"/
"Sold" in history — even though its note already says exactly what
happened ("Bought 0.008 units of QQQ"). Backfills by matching that note
pattern, which investing_service has used unchanged since it was built.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

debt_transactions = sa.table(
    "debt_transactions",
    sa.column("note", sa.String),
    sa.column("is_investment", sa.Boolean),
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        debt_transactions.update()
        .where(
            sa.or_(
                debt_transactions.c.note.op("~")(r"^Bought [0-9.]+ units of \S+$"),
                debt_transactions.c.note.op("~")(r"^Sold [0-9.]+ units of \S+$"),
            )
        )
        .values(is_investment=True)
    )


def downgrade() -> None:
    # Best-effort backfill of previously-missing data — not worth reversing.
    pass
