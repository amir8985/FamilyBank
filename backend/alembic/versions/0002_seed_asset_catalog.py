"""seed asset catalog

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.services.catalog_service import SEED_ASSETS

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# asyncpg (unlike psycopg2) won't implicitly cast a VARCHAR bind param to
# an enum column — the column type here has to match asset_kind exactly,
# with create_type=False since 0001 already created the Postgres type.
asset_catalog = sa.table(
    "asset_catalog",
    sa.column("symbol", sa.String),
    sa.column("display_name", sa.String),
    sa.column("kind", postgresql.ENUM("stock", "basket", name="asset_kind", create_type=False)),
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
