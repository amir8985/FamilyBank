"""Static v1 asset catalog — 20 kid-recognizable stocks + 5 baskets (spec
section 3). Seeded via the Alembic seed migration (0002, descriptions
updated in 0004).
"""

from app.models.catalog import AssetKind

SEED_ASSETS: list[dict] = [
    # -- Stocks (20) --
    {"symbol": "AAPL", "display_name": "Apple", "kind": AssetKind.STOCK, "description": "Apple makes the iPhone, iPad, Mac computers, and Apple Watch. It's one of the most valuable companies in the world and also runs the App Store."},
    {"symbol": "MSFT", "display_name": "Microsoft", "kind": AssetKind.STOCK, "description": "Microsoft makes Windows, the operating system on most computers, along with Xbox game consoles and Minecraft. It's also a huge player in cloud computing, which quietly powers many other apps and websites."},
    {"symbol": "GOOGL", "display_name": "Google", "kind": AssetKind.STOCK, "description": "Google runs the world's most popular search engine, along with YouTube, Gmail, and Android phones. Its parent company, Alphabet, is one of the biggest tech companies on Earth."},
    {"symbol": "AMZN", "display_name": "Amazon", "kind": AssetKind.STOCK, "description": "Amazon started as an online bookstore and grew into one of the world's biggest shopping websites. It also runs a huge cloud computing business that powers apps like Netflix behind the scenes."},
    {"symbol": "TSLA", "display_name": "Tesla", "kind": AssetKind.STOCK, "description": "Tesla makes electric cars, solar panels, and batteries. It's led by Elon Musk and is one of the most talked-about car companies in the world."},
    {"symbol": "DIS", "display_name": "Disney", "kind": AssetKind.STOCK, "description": "Disney makes movies, owns Pixar and Marvel, and runs theme parks around the world. It's also home to the Disney+ streaming service."},
    {"symbol": "NKE", "display_name": "Nike", "kind": AssetKind.STOCK, "description": "Nike makes sneakers, sportswear, and equipment worn by athletes everywhere. Its swoosh logo is one of the most recognized symbols in the world."},
    {"symbol": "MCD", "display_name": "McDonald's", "kind": AssetKind.STOCK, "description": "McDonald's is the world's biggest fast-food restaurant chain, famous for burgers, fries, and the Golden Arches. It has restaurants in almost every country on Earth."},
    {"symbol": "KO", "display_name": "Coca-Cola", "kind": AssetKind.STOCK, "description": "Coca-Cola makes the classic soda you've probably tasted, along with hundreds of other drinks sold worldwide. It's one of the most recognized brands on the planet."},
    {"symbol": "SBUX", "display_name": "Starbucks", "kind": AssetKind.STOCK, "description": "Starbucks is a coffee shop chain found in cities all over the world. Beyond coffee, it sells teas, snacks, and its famous holiday cups."},
    {"symbol": "NFLX", "display_name": "Netflix", "kind": AssetKind.STOCK, "description": "Netflix is a streaming service where people watch movies and TV shows on their phones, tablets, and TVs. It also makes its own original shows and movies."},
    {"symbol": "META", "display_name": "Meta", "kind": AssetKind.STOCK, "description": "Meta owns Instagram, WhatsApp, and Facebook — apps billions of people use to share photos and message each other. It's also investing heavily in virtual reality headsets."},
    {"symbol": "SONY", "display_name": "Sony", "kind": AssetKind.STOCK, "description": "Sony makes the PlayStation game console, along with TVs, cameras, and headphones. It's also a major music and movie studio."},
    {"symbol": "SPOT", "display_name": "Spotify", "kind": AssetKind.STOCK, "description": "Spotify is a music and podcast streaming app used by hundreds of millions of people. It lets you listen to almost any song instantly instead of buying albums."},
    {"symbol": "PYPL", "display_name": "PayPal", "kind": AssetKind.STOCK, "description": "PayPal lets people and businesses send and receive money online. It's one of the most widely used ways to pay for things on the internet."},
    {"symbol": "HAS", "display_name": "Hasbro", "kind": AssetKind.STOCK, "description": "Hasbro makes classic toys and games like Monopoly, Transformers, and My Little Pony. It's been making games families play together for generations."},
    {"symbol": "MAT", "display_name": "Mattel", "kind": AssetKind.STOCK, "description": "Mattel makes Barbie dolls and Hot Wheels toy cars, two of the most famous toy brands in the world. It's also made movies based on its toys."},
    {"symbol": "RBLX", "display_name": "Roblox", "kind": AssetKind.STOCK, "description": "Roblox is a platform where kids and teens play and build their own games. Millions of people log in every day to hang out and create things together."},
    {"symbol": "ABNB", "display_name": "Airbnb", "kind": AssetKind.STOCK, "description": "Airbnb lets people book a room or a whole house to stay in, hosted by regular people instead of a hotel chain. It's changed the way many people travel."},
    {"symbol": "UBER", "display_name": "Uber", "kind": AssetKind.STOCK, "description": "Uber lets you request a ride or order food delivery from an app on your phone. It operates in cities all over the world."},
    # -- Baskets (5) --
    {"symbol": "VOO", "display_name": "S&P 500 Fund", "kind": AssetKind.BASKET, "description": "This fund owns a small piece of the 500 biggest companies in the United States, including Apple, Microsoft, and Amazon. Instead of betting on just one company, you own a slice of all of them at once."},
    {"symbol": "QQQ", "display_name": "Nasdaq 100 Fund", "kind": AssetKind.BASKET, "description": "This fund owns a slice of 100 of the biggest tech-focused companies, like Apple, Google, and Tesla. It's a popular way to invest in the tech industry all at once."},
    {"symbol": "VT", "display_name": "World Fund", "kind": AssetKind.BASKET, "description": "This fund owns a small piece of thousands of companies from countries all over the world, not just the US. It's one of the most spread-out ways to invest."},
    {"symbol": "TA35.TA", "display_name": "Tel Aviv 35", "kind": AssetKind.BASKET, "description": "This tracks the 35 largest companies listed on the Tel Aviv Stock Exchange in Israel. It's a way to invest in Israel's biggest businesses all at once."},
    {"symbol": "^STOXX", "display_name": "Europe 600", "kind": AssetKind.BASKET, "description": "This tracks 600 companies from across Europe, from big countries like Germany and France to smaller ones too. It's a way to invest in European business all at once."},
]
