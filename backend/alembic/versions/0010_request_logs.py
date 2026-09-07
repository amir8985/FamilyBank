"""add request_logs table

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "request_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_request_logs_family_id", "request_logs", ["family_id"])
    op.create_index("ix_request_logs_created_at", "request_logs", ["created_at"])
    op.create_index("ix_request_logs_path_duration", "request_logs", ["path", "duration_ms"])


def downgrade() -> None:
    op.drop_index("ix_request_logs_path_duration", table_name="request_logs")
    op.drop_index("ix_request_logs_created_at", table_name="request_logs")
    op.drop_index("ix_request_logs_family_id", table_name="request_logs")
    op.drop_table("request_logs")
