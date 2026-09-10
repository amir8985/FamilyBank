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

/** Compounded yearly equivalent of a monthly percentage rate —
 * 2%/month is ~26.8%/year, not 24%. Mirrors savings_service.annual_rate
 * on the backend; used only for the "≈ X%/year" hint next to a rate the
 * parent is setting. */
export function annualFromMonthly(monthlyPct: string | number): number {
  const m = typeof monthlyPct === "string" ? Number(monthlyPct) : monthlyPct;
  return (Math.pow(1 + m / 100, 12) - 1) * 100;
}

export function formatPct(pct: string | number | null): string | null {
  if (pct === null) return null;
  const value = typeof pct === "string" ? Number(pct) : pct;
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

/** Drops the trailing zeros the API's 8-decimal-place Numeric column
 * always includes ("0.00400000" -> "0.004") rather than the fixed
 * 3-decimal padding an earlier version used ("0.02" -> "0.020", which
 * read as a confusing extra zero). */
export function trimUnits(units: string | number): string {
  const value = typeof units === "string" ? Number(units) : units;
  return value.toString();
}

/** Splits a formatted amount around its currency symbol, so callers can
 * render the symbol in a different font than the numeral — needed
 * because Source Serif 4 (the numeral font) lacks a proper ₪ glyph and
 * falls back to a mismatched system serif on Android. */
export function formatMoneyParts(
  amount: string | number,
  currency: string
): { before: string; symbol: string; after: string } {
  const value = typeof amount === "string" ? Number(amount) : amount;
  try {
    const parts = new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      currencyDisplay: "symbol",
    }).formatToParts(value);
    const symbolIndex = parts.findIndex((p) => p.type === "currency");
    return {
      before: parts
        .slice(0, symbolIndex)
        .map((p) => p.value)
        .join(""),
      symbol: parts[symbolIndex]?.value ?? currency,
      after: parts
        .slice(symbolIndex + 1)
        .map((p) => p.value)
        .join(""),
    };
  } catch {
    // Matches formatMoney's own fallback ordering ("12.34 USD").
    return { before: `${value.toFixed(2)} `, symbol: currency, after: "" };
  }
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

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

/** Ordinal suffix for a day-of-month, e.g. 1 → "st", 22 → "nd". */
export function ordinal(n: number): string {
  if (n % 10 === 1 && n !== 11) return "st";
  if (n % 10 === 2 && n !== 12) return "nd";
  if (n % 10 === 3 && n !== 13) return "rd";
  return "th";
}

/** Human label for an allowance schedule, e.g. "every Monday" or
 * "on the 1st of the month". `payday` is 0–6 for weekly, 1–28 for monthly. */
export function allowanceScheduleLabel(cadence: "weekly" | "monthly", payday: number): string {
  if (cadence === "weekly") return `every ${WEEKDAYS[payday] ?? "week"}`;
  return `on the ${payday}${ordinal(payday)} of each month`;
}

export function initial(name: string): string {
  return name.trim().charAt(0).toUpperCase();
}

export function formatUpdatedAt(iso: string | null): string {
  if (!iso) return "price pending";
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(diffMs / 60_000);
  if (minutes < 1) return "Updated just now";
  if (minutes < 60) return `Updated ${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `Updated ${hours}h ago`;
  const days = Math.round(hours / 24);
  return `Updated ${days}d ago`;
}

/** Picks a "kid-friendly" default unit count so the initial cost lands
 * between 1 and 10 in the family's currency — e.g. a $2000 stock
 * defaults to 0.001 units (≈$2), a $5 stock defaults to 1 unit. Mirrors
 * the original project's `_unit_step_for_price` (spec section 6). */
export function defaultUnitStep(pricePerUnit: number): number {
  if (!Number.isFinite(pricePerUnit) || pricePerUnit <= 0) return 1;
  let step = 1;
  if (pricePerUnit * step > 10) {
    while (pricePerUnit * step > 10) step /= 10;
  } else {
    while (pricePerUnit * step < 1) step *= 10;
  }
  return step;
}
