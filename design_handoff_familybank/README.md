# Handoff: FamilyBank — Brand & Core Screens (v1)

## Overview
FamilyBank is an app for parents to track allowance/debt owed to their kids, with a feature letting kids "invest" that virtual balance in real stocks/index funds at real market prices (no real broker, no real money movement — see `FamilyBank_spec.md`). This package covers: a brand identity, a marketing landing page, and the four core in-app screens for v1 (parent-only access, no kid login).

## About the Design Files
The `.dc.html` files in this bundle are **design references built in HTML** (Design Components — a prototyping format, not a framework). They show intended look, layout, and copy — not production code to copy directly. Recreate these designs in the target codebase's actual stack per `FamilyBank_architecture.md` (Next.js frontend) using its existing patterns/component library, or set one up if none exists yet, matching the visual spec below pixel-for-pixel.

`ios-frame.jsx` is only a prototyping device-bezel wrapper used to preview the screens as a phone — it is not meant to ship; the frame chrome (status bar, home indicator) should come from the real OS/browser, not this file.

## Fidelity
**High-fidelity.** Colors, typography, spacing, and copy below are final for this pass — implement pixel-precisely. Data shown (kid names, balances, holdings, prices) is placeholder/sample data; wire to the real API shape in `FamilyBank_architecture.md` section 3.

## Brand
- **Logo mark**: a filled circle badge, deep emerald fill, 2px brass-gold ring border, centered "FB" monogram set in Source Serif 4 Semibold, gold-colored. Wordmark "FamilyBank" set in Source Serif 4 Semibold next to the mark, ink-emerald color, letter-spacing -0.01em to -0.02em.
- **Palette** (see `FamilyBank Brand Directions.dc.html`, option `3a`, for full swatches):
  - Emerald (primary/ink): `oklch(25% 0.06 155)`
  - Brass gold (accent): `oklch(65% 0.11 75)`
  - Cream (background): `oklch(97% 0.01 100)`
  - Muted text: `oklch(45% 0.03 155)` / `oklch(40% 0.03 155)`
  - Functional (not brand) colors for gains/losses: positive uses brass `oklch(48% 0.09 75)`, negative uses `oklch(55% 0.15 25)` (a muted red)
- **Typography**: Source Serif 4 (500/600 weight) for all headlines, balances, and monetary amounts. Work Sans (400–700) for all UI labels, body copy, and buttons. Load both from Google Fonts.
- Three earlier directions were explored and rejected (see the same file's turns 1 and 2) — keep for reference only, do not implement.

## Screens / Views

### 1. Marketing landing page (`FamilyBank Landing Page.dc.html`)
Public-facing page, not behind auth. Sections top to bottom: sticky nav (logo left, 3 text links center, "Get started" button right — nav links hide under 860px), hero (headline + subhead + two CTAs left, stacked mock UI cards right — stacks to a single column under 860px), a thin trust-strip bar (4 short claims), a 3-column "How it works" feature grid (collapses to 1 column on mobile), a full-bleed emerald "this is a lesson, not a brokerage" trust section, and a simple footer. All copy in the file is final; treat it as ship-ready.

### 2. Parent home — balances (`FamilyBank App Screens.dc.html`, frame 1)
Purpose: the parent's landing screen — see what's owed to each kid, act on it, jump into a kid's investments.
- Header: logo mark + wordmark (left), settings icon circle (right)
- "You owe" total in large serif type
- Scrollable list of kid cards, one per kid: avatar-initial circle (color varies per kid, decorative only) + name + balance (top row); "+ Add" (filled emerald-tint pill) / "– Deduct" (outlined pill) actions (second row); a footer row inside the card showing that kid's portfolio value + day change, and an "Investments →" link that opens screen 3 for that kid
- Dashed "+ Add a kid" row at the bottom of the list

### 3. Add / deduct balance (`FamilyBank App Screens.dc.html`, frame 2)
Purpose: a parent adds to or deducts from one kid's debt balance, with a free-text note (spec 2.2).
- Presented as a bottom sheet over a dimmed home screen
- Segmented Add/Deduct control (Add selected = solid emerald pill)
- Large amount display/input in serif type
- Optional note field
- "New balance" preview line (current + delta computed live)
- Full-width "Confirm" button — writes a `debt_transactions` row per the architecture doc

### 4. Kid portfolio — "My Investments" (`FamilyBank App Screens.dc.html`, frame 3)
Purpose: view one kid's holdings + cash, entry point to buying (spec 2.3).
- Back chevron + "{Kid}'s Investments" title
- Total portfolio value (holdings + cash) in large serif, with today's $ and % change
- Segmented tab control: "My Investments" (active) / "Buy" — switches the content below, no navigation
- Holdings list: one row per holding — ticker badge, display name, units owned (left); current value + day % change, colored (right)
- Trailing "Cash available" row, always last, no chevron

### 5. Buy flow (`FamilyBank App Screens.dc.html`, frame 4)
Purpose: buy a specific stock/basket for a kid, converted to the family's home currency, with an explicit cost preview before confirming (spec 2.3 step 4).
- Back chevron + "Buy {TICKER}" title
- Stock name + "live price, in $" caption + current price (already converted to home currency) top right
- Small bar-chart price history strip (native-currency lookback per spec 2.4 — note in original currency, not shown converted)
- Toggle: enter in "Amount (₪)" or "Units" — whichever tab is active is highlighted
- Large computed result: the cost in home currency, with the equivalent unit count as a caption ("≈ 0.400 units of AAPL")
- A short reinforcement line: this is virtual money at a real price, not a real purchase (spec section 0's framing — must appear somewhere on this screen, exact wording flexible)
- "Cash available after" preview line
- Full-width "Buy for ₪X" confirm button — disabled if the amount exceeds cash available (not shown in the mock; add as a validation state)

## Interactions & Behavior
- Kid card → "Investments →" navigates to screen 3 for that kid
- "+ Add" / "– Deduct" opens screen 2's sheet pre-set to that action
- Screen 3's "Buy" tab switches to a stock list (not mocked — same list style as the asset catalog, spec section 3); tapping a stock opens screen 4 for it
- Screen 4's Amount/Units toggle recalculates the paired value live as the user types in either field
- All monetary amounts are shown in the family's base currency (already converted server-side per architecture 5.1/2 §"Currency storage principle") — the client never does FX math
- No loading/error states are mocked; add standard skeleton/error treatment consistent with the rest of the target app

## State Management
- Kid list + balances: fetched once per home-screen load (`GET` equivalent of the kids/debt endpoints)
- Selected kid + selected holding: route/screen params
- Buy form: local state for `mode` (amount|units), `inputValue`, derived `units`/`cost` (computed from live `price_cache` + `fx_rates_cache`, per architecture §1)
- Add/Deduct sheet: local state for `direction`, `amount`, `note`

## Design Tokens
- Colors: emerald `oklch(25% 0.06 155)`, brass `oklch(65% 0.11 75)`, cream bg `oklch(97% 0.01 100)`, card white `#fff`, hairline border `rgba(0,0,0,.06)`–`rgba(0,0,0,.12)`, muted text `oklch(45% 0.03 155)` / `oklch(40% 0.03 155)`, positive `oklch(48% 0.09 75)`, negative `oklch(55% 0.15 25)`
- Radius: 8–10px small controls/pills, 14–16px cards, 24px sheet top corners, 50% avatars/badge
- Type: Source Serif 4 600 for money/headlines (17–40px depending on context), Work Sans 400–700 for everything else (12–17px)
- Spacing: 16–20px screen side padding, 8–14px gaps between stacked elements, 12–16px card internal padding

## Assets
No real imagery used — all avatars/marks are CSS shapes with initials. Ticker "badges" (AAPL/VOO) are plain colored squares with text; swap for real logos/icons if available, or keep as a simple fallback style.

## Files
- `FamilyBank Brand Directions.dc.html` — brand exploration (3 rounds); final direction is option `3a` in turn 3
- `FamilyBank Landing Page.dc.html` — marketing page, responsive
- `FamilyBank App Screens.dc.html` — the 4 in-app screens described above
- `ios-frame.jsx` — prototyping-only phone bezel, not for production
- `FamilyBank_spec.md`, `FamilyBank_architecture.md` — original product spec + architecture docs
- `screenshots/` — static PNG captures of each file above, for quick reference without opening HTML
