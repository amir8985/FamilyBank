"""add family boost_buffer_rate, price_ticks, investment_lots

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: no boost until a parent explicitly sets one. Family-wide
    # by design (see models/family.py) — every open lot at any moment
    # shares this exact rate, enforced by only allowing a change while no
    # kid holds any stock.
    op.add_column(
        "families",
        sa.Column("boost_buffer_rate", sa.Numeric(6, 3), nullable=True),
    )

    op.create_table(
        "price_ticks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(), sa.ForeignKey("asset_catalog.symbol"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(14, 4), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
    )
    op.create_index("ix_price_ticks_symbol", "price_ticks", ["symbol"])
    op.create_index("ix_price_ticks_observed_at", "price_ticks", ["observed_at"])
    # boost_service always queries "this symbol's ticks since some
    # timestamp" — a composite index matches that access pattern directly
    # instead of relying on the two single-column indexes above.
    op.create_index("ix_price_ticks_symbol_observed_at", "price_ticks", ["symbol", "observed_at"])

    op.create_table(
        "investment_lots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "kid_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kids.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("symbol", sa.String(), sa.ForeignKey("asset_catalog.symbol"), nullable=False),
        sa.Column("units", sa.Numeric(20, 8), nullable=False),
        sa.Column("purchase_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("purchase_currency", sa.String(), nullable=False),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("buffer_rate", sa.Numeric(6, 3), nullable=True),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sale_value", sa.Numeric(14, 4), nullable=True),
        sa.Column("sale_currency", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_investment_lots_kid_id", "investment_lots", ["kid_id"])
    op.create_index("ix_investment_lots_symbol", "investment_lots", ["symbol"])
    op.create_index("ix_investment_lots_is_open", "investment_lots", ["is_open"])


def downgrade() -> None:
    op.drop_table("investment_lots")
    op.drop_table("price_ticks")
    op.drop_column("families", "boost_buffer_rate")
