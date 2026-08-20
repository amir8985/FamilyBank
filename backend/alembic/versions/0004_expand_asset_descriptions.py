"""expand asset catalog descriptions to 2-3 kid-friendly sentences

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.services.catalog_service import SEED_ASSETS

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

asset_catalog = sa.table(
    "asset_catalog",
    sa.column("symbol", sa.String),
    sa.column("description", sa.String),
)

# Snapshot of the short descriptions 0002 originally seeded, so downgrade
# can restore them exactly rather than guessing.
_OLD_DESCRIPTIONS = {
    "AAPL": "Makes the iPhone, iPad, and Mac.",
    "MSFT": "Windows, Xbox, and Minecraft.",
    "GOOGL": "Search, YouTube, and Android.",
    "AMZN": "Online shopping and delivery.",
    "TSLA": "Electric cars and batteries.",
    "DIS": "Movies, Pixar, and theme parks.",
    "NKE": "Sneakers and sportswear.",
    "MCD": "Burgers and fries, worldwide.",
    "KO": "The classic soda.",
    "SBUX": "Coffee shops everywhere.",
    "NFLX": "Movies and shows you stream.",
    "META": "Instagram and WhatsApp's parent company.",
    "SONY": "PlayStation and electronics.",
    "SPOT": "Music and podcast streaming.",
    "PYPL": "Sending money online.",
    "HAS": "Toys and games like Monopoly.",
    "MAT": "Makes Barbie and Hot Wheels.",
    "RBLX": "The game-building platform.",
    "ABNB": "Booking places to stay.",
    "UBER": "Rides and food delivery.",
    "VOO": "A slice of the 500 biggest US companies.",
    "QQQ": "100 of the biggest tech companies.",
    "VT": "A slice of companies from all over the world.",
    "TA35.TA": "The 35 biggest companies on the Tel Aviv exchange.",
    "^STOXX": "600 companies from across Europe.",
}


def upgrade() -> None:
    conn = op.get_bind()
    for asset in SEED_ASSETS:
        conn.execute(
            asset_catalog.update()
            .where(asset_catalog.c.symbol == asset["symbol"])
            .values(description=asset["description"])
        )


def downgrade() -> None:
    conn = op.get_bind()
    for symbol, description in _OLD_DESCRIPTIONS.items():
        conn.execute(
            asset_catalog.update().where(asset_catalog.c.symbol == symbol).values(description=description)
        )
