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
  total_invested: string;
  kids: KidSummary[];
  // When the scheduler last refreshed the prices behind portfolio values
  // (~5x/day). ISO string. Lets the client treat this payload as good
  // until the next refresh instead of re-fetching on every navigation.
  prices_as_of: string | null;
};

export type FamilySettings = {
  base_currency: string;
  onboarding_completed: boolean;
  // Monthly %, e.g. "3.000" — null means boost is off. Applies to every
  // kid in the family (see backend/app/models/family.py's docstring).
  boost_buffer_rate: string | null;
};

export type KidCurrencyPreview = {
  kid_id: string;
  name: string;
  old_cash_balance: string;
  new_cash_balance: string;
};

export type CurrencyChangePreviewOut = {
  from_currency: string;
  to_currency: string;
  rate: string;
  kids: KidCurrencyPreview[];
};

export type DebtTransactionType = "add" | "deduct";

export type DebtTransactionOut = {
  id: string;
  type: DebtTransactionType;
  amount: string;
  note: string | null;
  is_adjustment: boolean;
  is_investment: boolean;
  is_savings: boolean;
  is_allowance: boolean;
  currency: string;
  previous_currency: string;
  balance_before: string;
  balance_after: string;
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
  price_updated_at: string | null;
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
  since_purchase_pct: string | null;
  // Present only for a purchase made after the boost feature shipped
  // (an investment_lot) — null for a pre-existing avg-cost holding.
  lot_id: string | null;
  is_boosted: boolean;
};

export type LotPointOut = {
  observed_at: string;
  value: string;
};

export type LotDetailOut = {
  lot_id: string;
  symbol: string;
  display_name: string;
  description: string;
  units: string;
  purchase_price: string;
  purchase_currency: string;
  purchased_at: string;
  buffer_rate: string | null;
  is_open: boolean;
  sold_at: string | null;
  current_value: string;
  since_purchase_pct: string | null;
  series: LotPointOut[];
};

export type SavingsPlanOut = {
  id: string;
  name: string;
  monthly_rate: string;
  annual_rate: string;
  lock_months: number;
  is_active: boolean;
  open_deposit_count: number;
  preset_key: string | null;
};

export type SavingsPresetOut = {
  key: string;
  name: string;
  monthly_rate: string;
  annual_rate: string;
  lock_months: number;
  kind: "flexible" | "locked";
};

export type PlanDepositOut = {
  kid_id: string;
  kid_name: string;
  current_value: string;
  currency: string;
  is_locked: boolean;
  is_matured: boolean;
};

export type DepositablePlanOut = {
  id: string;
  name: string;
  monthly_rate: string;
  annual_rate: string;
  lock_months: number;
};

export type SavingsDepositOut = {
  deposit_id: string;
  plan_name: string;
  monthly_rate: string;
  annual_rate: string;
  lock_months: number;
  is_locked: boolean;
  matures_at: string | null;
  is_matured: boolean;
  principal: string;
  current_value: string;
  accrued_interest: string;
  currency: string;
  opened_at: string;
};

export type SavingsOverviewOut = {
  savings_value: string;
  deposits: SavingsDepositOut[];
  plans: DepositablePlanOut[];
};

export type SavingsDepositDetailOut = SavingsDepositOut & {
  is_open: boolean;
  closed_at: string | null;
  series: LotPointOut[];
  series_currency: string;
};

export type PortfolioOut = {
  kid_id: string;
  kid_name: string;
  cash_available: string;
  holdings_value: string;
  savings_value: string;
  total_value: string;
  total_day_change_amount: string;
  total_day_change_pct: string | null;
  holdings: HoldingOut[];
  prices_as_of: string | null;
  // Family-wide monthly boost rate (%), or null when boost is off — lets
  // the buy screen preview a boosted lot without a /family/settings call.
  boost_buffer_rate: string | null;
};

export type AllowanceCadence = "weekly" | "monthly";

export type AllowancePaymentOut = {
  amount: string;
  currency: string;
  paid_at: string;
};

export type AllowanceOut = {
  kid_id: string;
  kid_name: string;
  configured: boolean;
  is_active: boolean;
  amount: string | null;
  currency: string | null;
  cadence: AllowanceCadence | null;
  payday: number | null;
  next_payday: string | null;
  last_paid_at: string | null;
  recent_payments: AllowancePaymentOut[];
};

export type FamilyAllowancesOut = {
  base_currency: string;
  kids: AllowanceOut[];
};

export type AllowanceUpsert = {
  amount: number;
  cadence: AllowanceCadence;
  payday: number;
  is_active: boolean;
};

export type KidMe = {
  kid_id: string;
  public_id: string;
  name: string;
  avatar_color: string;
  family_id: string;
  base_currency: string;
};

export type KidInviteStatus = {
  has_pending_invite: boolean;
  sessions_active: boolean;
  expires_at: string | null;
};

export type KidInviteResult = {
  claim_url: string;
  pin: string;
  expires_at: string;
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
