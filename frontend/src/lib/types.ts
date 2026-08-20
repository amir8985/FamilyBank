// Mirrors backend/app/schemas/*.py. Decimal fields serialize as JSON
// strings (Pydantic v2 default) — parse with Number() for display only,
// never re-derive money math client-side (the server is the source of truth).

export type KidSummary = {
  id: string;
  name: string;
  avatar_color: string;
  cash_balance: string;
  portfolio_value: string;
  portfolio_day_change_pct: string | null;
};

export type FamilyHome = {
  base_currency: string;
  total_owed: string;
  kids: KidSummary[];
};

export type DebtTransactionType = "add" | "deduct";

export type DebtTransactionOut = {
  id: string;
  type: DebtTransactionType;
  amount: string;
  note: string | null;
  created_at: string;
};

export type DebtUpdateResult = {
  transaction: DebtTransactionOut;
  new_balance: string;
};

export type AssetKind = "stock" | "basket";

export type AssetOut = {
  symbol: string;
  display_name: string;
  kind: AssetKind;
  description: string;
  price: string | null;
  price_currency: string | null;
  day_change_pct: string | null;
};

export type AssetDetailOut = AssetOut & {
  native_currency: string | null;
  history: { date: string; close: number }[];
};

export type HoldingOut = {
  symbol: string;
  display_name: string;
  units: string;
  current_value: string;
  day_change_pct: string | null;
};

export type PortfolioOut = {
  kid_id: string;
  kid_name: string;
  cash_available: string;
  holdings_value: string;
  total_value: string;
  total_day_change_amount: string;
  total_day_change_pct: string | null;
  holdings: HoldingOut[];
};

export type BuySellQuoteResponse = {
  symbol: string;
  units: string;
  cost: string;
  price_per_unit: string;
  currency: string;
  cash_available_after: string;
};

export type InvestmentTransactionType = "buy" | "sell";

export type InvestmentTransactionOut = {
  id: string;
  symbol: string;
  type: InvestmentTransactionType;
  units: string;
  price: string;
  price_currency: string;
  created_at: string;
};
