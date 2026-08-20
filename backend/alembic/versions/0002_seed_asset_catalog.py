"""seed asset catalog

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.services.catalog_service import SEED_ASSETS

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

asset_catalog = sa.table(
    "asset_catalog",
    sa.column("symbol", sa.String),
    sa.column("display_name", sa.String),
    sa.column("kind", sa.String),
    sa.column("description", sa.String),
)


def upgrade() -> None:
    op.bulk_insert(
        asset_catalog,
        [
            {
                "symbol": a["symbol"],
                "display_name": a["display_name"],
                "kind": a["kind"].value,
                "description": a["description"],
            }
            for a in SEED_ASSETS
        ],
    )


def downgrade() -> None:
    conn = op.get_bind()
    symbols = [a["symbol"] for a in SEED_ASSETS]
    conn.execute(asset_catalog.delete().where(asset_catalog.c.symbol.in_(symbols)))
