"""kid public_id + multi-device sessions

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-09

Second pass on kid login:
  - kids.public_id: an opaque per-kid handle for the kid app's URLs, so
    the primary key is never exposed in a link the kid keeps.
  - kids.sessions_active: whether any device currently holds a session
    (drives the parent's "sign out of all devices" button).
  - kid_invites.consumed_at -> first_claimed_at: an invite is now
    multi-use within its window (phone + laptop off one link), so the
    timestamp is informational, not a lock.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# A DB-side default (random 16-hex handle — md5 is built in, no extension
# needed) so an INSERT that doesn't name public_id still succeeds. That
# matters because this migration lands on the shared dev DB before
# kid-pages merges: every OTHER branch's model still inserts kids without
# this column, and would hit a NOT NULL violation without the default.
# The Python-side default in the model (_new_public_id) takes precedence
# for this branch's own inserts.
_PUBLIC_ID_DEFAULT = sa.text("left(md5(random()::text || clock_timestamp()::text), 16)")


def upgrade() -> None:
    # NOT NULL + a volatile default → Postgres rewrites the table and
    # evaluates the default per existing row, so every current kid gets a
    # distinct handle (needed for the unique index below).
    op.add_column(
        "kids",
        sa.Column("public_id", sa.String(), nullable=False, server_default=_PUBLIC_ID_DEFAULT),
    )
    op.create_index("ix_kids_public_id", "kids", ["public_id"], unique=True)

    op.add_column(
        "kids",
        sa.Column("sessions_active", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.alter_column("kid_invites", "consumed_at", new_column_name="first_claimed_at")


def downgrade() -> None:
    op.alter_column("kid_invites", "first_claimed_at", new_column_name="consumed_at")
    op.drop_column("kids", "sessions_active")
    op.drop_index("ix_kids_public_id", table_name="kids")
    op.drop_column("kids", "public_id")
