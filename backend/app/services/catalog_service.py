"""Static v1 asset catalog — 20 kid-recognizable stocks + 5 baskets (spec
section 3). Seeded via `python -m app.services.catalog_service seed` or
automatically by the Alembic seed migration.
"""

from app.models.catalog import AssetKind

SEED_ASSETS: list[dict] = [
    # -- Stocks (20) --
    {"symbol": "AAPL", "display_name": "Apple", "kind": AssetKind.STOCK, "description": "Makes the iPhone, iPad, and Mac."},
    {"symbol": "MSFT", "display_name": "Microsoft", "kind": AssetKind.STOCK, "description": "Windows, Xbox, and Minecraft."},
    {"symbol": "GOOGL", "display_name": "Google", "kind": AssetKind.STOCK, "description": "Search, YouTube, and Android."},
    {"symbol": "AMZN", "display_name": "Amazon", "kind": AssetKind.STOCK, "description": "Online shopping and delivery."},
    {"symbol": "TSLA", "display_name": "Tesla", "kind": AssetKind.STOCK, "description": "Electric cars and batteries."},
    {"symbol": "DIS", "display_name": "Disney", "kind": AssetKind.STOCK, "description": "Movies, Pixar, and theme parks."},
    {"symbol": "NKE", "display_name": "Nike", "kind": AssetKind.STOCK, "description": "Sneakers and sportswear."},
    {"symbol": "MCD", "display_name": "McDonald's", "kind": AssetKind.STOCK, "description": "Burgers and fries, worldwide."},
    {"symbol": "KO", "display_name": "Coca-Cola", "kind": AssetKind.STOCK, "description": "The classic soda."},
    {"symbol": "SBUX", "display_name": "Starbucks", "kind": AssetKind.STOCK, "description": "Coffee shops everywhere."},
    {"symbol": "NFLX", "display_name": "Netflix", "kind": AssetKind.STOCK, "description": "Movies and shows you stream."},
    {"symbol": "META", "display_name": "Meta", "kind": AssetKind.STOCK, "description": "Instagram and WhatsApp's parent company."},
    {"symbol": "SONY", "display_name": "Sony", "kind": AssetKind.STOCK, "description": "PlayStation and electronics."},
    {"symbol": "SPOT", "display_name": "Spotify", "kind": AssetKind.STOCK, "description": "Music and podcast streaming."},
    {"symbol": "PYPL", "display_name": "PayPal", "kind": AssetKind.STOCK, "description": "Sending money online."},
    {"symbol": "HAS", "display_name": "Hasbro", "kind": AssetKind.STOCK, "description": "Toys and games like Monopoly."},
    {"symbol": "MAT", "display_name": "Mattel", "kind": AssetKind.STOCK, "description": "Makes Barbie and Hot Wheels."},
    {"symbol": "RBLX", "display_name": "Roblox", "kind": AssetKind.STOCK, "description": "The game-building platform."},
    {"symbol": "ABNB", "display_name": "Airbnb", "kind": AssetKind.STOCK, "description": "Booking places to stay."},
    {"symbol": "UBER", "display_name": "Uber", "kind": AssetKind.STOCK, "description": "Rides and food delivery."},
    # -- Baskets (5) --
    {"symbol": "VOO", "display_name": "S&P 500 Fund", "kind": AssetKind.BASKET, "description": "A slice of the 500 biggest US companies."},
    {"symbol": "QQQ", "display_name": "Nasdaq 100 Fund", "kind": AssetKind.BASKET, "description": "100 of the biggest tech companies."},
    {"symbol": "VT", "display_name": "World Fund", "kind": AssetKind.BASKET, "description": "A slice of companies from all over the world."},
    {"symbol": "TA35.TA", "display_name": "Tel Aviv 35", "kind": AssetKind.BASKET, "description": "The 35 biggest companies on the Tel Aviv exchange."},
    {"symbol": "^STOXX", "display_name": "Europe 600", "kind": AssetKind.BASKET, "description": "600 companies from across Europe."},
]
