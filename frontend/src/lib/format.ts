export function formatMoney(amount: string | number, currency: string): string {
  const value = typeof amount === "string" ? Number(amount) : amount;
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      currencyDisplay: "symbol",
    }).format(value);
  } catch {
    return `${value.toFixed(2)} ${currency}`;
  }
}

export function formatSignedMoney(amount: string | number, currency: string): string {
  const value = typeof amount === "string" ? Number(amount) : amount;
  const formatted = formatMoney(Math.abs(value), currency);
  return value < 0 ? `-${formatted}` : `+${formatted}`;
}

export function formatPct(pct: string | number | null): string | null {
  if (pct === null) return null;
  const value = typeof pct === "string" ? Number(pct) : pct;
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

export function formatUnits(units: string | number): string {
  const value = typeof units === "string" ? Number(units) : units;
  // Whole numbers read as "2 units", fractional as "0.400 units" (handoff copy).
  const isWhole = Number.isInteger(value);
  return isWhole ? `${value}` : value.toFixed(3);
}

export function currencySymbol(currency: string): string {
  try {
    const parts = new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      currencyDisplay: "symbol",
    }).formatToParts(0);
    return parts.find((p) => p.type === "currency")?.value ?? currency;
  } catch {
    return currency;
  }
}

export function initial(name: string): string {
  return name.trim().charAt(0).toUpperCase();
}
