"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "families",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("base_currency", sa.String(), nullable=False, server_default="ILS"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "family_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("families.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("google_sub", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_family_id", "users", ["family_id"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_google_sub", "users", ["google_sub"])

    op.create_table(
        "kids",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "family_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("families.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("avatar_color", sa.String(), nullable=False, server_default="amber"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_kids_family_id", "kids", ["family_id"])

    debt_txn_type = postgresql.ENUM("add", "deduct", name="debt_transaction_type", create_type=False)
    debt_txn_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "debt_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "kid_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kids.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("type", debt_txn_type, nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_debt_transactions_kid_id", "debt_transactions", ["kid_id"])

    asset_kind = postgresql.ENUM("stock", "basket", name="asset_kind", create_type=False)
    asset_kind.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "asset_catalog",
        sa.Column("symbol", sa.String(), primary_key=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("kind", asset_kind, nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
    )

    op.create_table(
        "price_cache",
        sa.Column("symbol", sa.String(), sa.ForeignKey("asset_catalog.symbol"), primary_key=True),
        sa.Column("price", sa.Numeric(14, 4), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("history_json", postgresql.JSONB(), nullable=False, server_default="[]"),
    )

    op.create_table(
        "fx_rates_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("base_currency", sa.String(), nullable=False),
        sa.Column("quote_currency", sa.String(), nullable=False),
        sa.Column("rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("base_currency", "quote_currency", name="uq_fx_pair"),
    )

    inv_txn_type = postgresql.ENUM("buy", "sell", name="investment_transaction_type", create_type=False)
    inv_txn_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "investment_holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "kid_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kids.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("symbol", sa.String(), sa.ForeignKey("asset_catalog.symbol"), nullable=False),
        sa.Column("units", sa.Numeric(20, 8), nullable=False),
        sa.Column("avg_cost", sa.Numeric(14, 4), nullable=False),
        sa.Column("avg_cost_currency", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("kid_id", "symbol", name="uq_holding_kid_symbol"),
    )
    op.create_index("ix_investment_holdings_kid_id", "investment_holdings", ["kid_id"])
    op.create_index("ix_investment_holdings_symbol", "investment_holdings", ["symbol"])

    op.create_table(
        "investment_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "kid_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kids.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("symbol", sa.String(), sa.ForeignKey("asset_catalog.symbol"), nullable=False),
        sa.Column("units", sa.Numeric(20, 8), nullable=False),
        sa.Column("price", sa.Numeric(14, 4), nullable=False),
        sa.Column("price_currency", sa.String(), nullable=False),
        sa.Column("type", inv_txn_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_investment_transactions_kid_id", "investment_transactions", ["kid_id"])
    op.create_index("ix_investment_transactions_symbol", "investment_transactions", ["symbol"])


def downgrade() -> None:
    op.drop_table("investment_transactions")
    op.drop_table("investment_holdings")
    op.drop_table("fx_rates_cache")
    op.drop_table("price_cache")
    op.drop_table("asset_catalog")
    op.drop_table("debt_transactions")
    op.drop_table("kids")
    op.drop_table("users")
    op.drop_table("families")

    bind = op.get_bind()
    postgresql.ENUM(name="investment_transaction_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="asset_kind").drop(bind, checkfirst=True)
    postgresql.ENUM(name="debt_transaction_type").drop(bind, checkfirst=True)
