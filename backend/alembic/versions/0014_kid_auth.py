"""add kids.token_version, kid_invites

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-09

Kid-facing login (spec 4.1 v2). A parent generates a per-kid invite
(link + spoken PIN); the kid claims it once and gets a long-lived
session. token_version is the revocation lever — a claim bumps it, which
invalidates any session an old device still holds.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default "0" so every kid that predates this migration reads
    # as version 0 rather than NULL (the CLAUDE.md lesson: a new non-null
    # column that new code treats as always set).
    op.add_column(
        "kids",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "kid_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "kid_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kids.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim_token_hash", sa.String(), nullable=False),
        sa.Column("pin_salt", sa.String(), nullable=False),
        sa.Column("pin_hash", sa.String(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # One pending invite per kid — a new one replaces the old.
    op.create_index("ix_kid_invites_kid_id", "kid_invites", ["kid_id"], unique=True)
    op.create_index("ix_kid_invites_claim_token_hash", "kid_invites", ["claim_token_hash"])


def downgrade() -> None:
    op.drop_table("kid_invites")
    op.drop_column("kids", "token_version")
