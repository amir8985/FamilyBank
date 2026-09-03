"""backfill from/to currency on pre-existing adjustment rows

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-03

Migration 0006 added from_currency/to_currency but left every
is_adjustment row written before it with both columns NULL (adding a
column has no way to backfill data it never captured). Without this,
debts_db_service.list_transactions_with_currency crashes on any kid who
had a currency change before today, since it (with a note-parsing
fallback added alongside this migration) can't determine the row's real
currency. This backfill parses the same note text that fallback reads,
so after running, that fallback path is unused for existing data — it
only still matters for a database this migration hasn't reached yet.
"""
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

debt_transactions = sa.table(
    "debt_transactions",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("note", sa.String),
    sa.column("is_adjustment", sa.Boolean),
    sa.column("from_currency", sa.String),
    sa.column("to_currency", sa.String),
)

_NOTE_RE = re.compile(r"^Currency changed: (\w+) → (\w+)")


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(debt_transactions.c.id, debt_transactions.c.note).where(
            debt_transactions.c.is_adjustment.is_(True),
            debt_transactions.c.from_currency.is_(None),
        )
    ).fetchall()
    for row in rows:
        match = _NOTE_RE.match(row.note) if row.note else None
        if not match:
            continue
        conn.execute(
            debt_transactions.update()
            .where(debt_transactions.c.id == row.id)
            .values(from_currency=match.group(1), to_currency=match.group(2))
        )


def downgrade() -> None:
    # Best-effort backfill of previously-missing data — not worth reversing.
    pass
