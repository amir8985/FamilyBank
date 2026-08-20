"use client";

import { useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Sparkline } from "@/components/ui/sparkline";
import { PageHeader } from "@/components/ui/page-header";
import { SellSheet } from "@/components/sell-sheet";
import { api, ApiError } from "@/lib/api";
import { currencySymbol, defaultUnitStep, formatMoney, formatPct, formatUpdatedAt, trimUnits } from "@/lib/format";
import type { AssetDetailOut, BuySellQuoteResponse, HoldingOut, InvestmentTransactionOut } from "@/lib/types";

type Mode = "units" | "amount";

function decimalsForStep(step: number): number {
  if (step >= 1) return 0;
  return Math.round(-Math.log10(step));
}

export function BuyFormClient({
  kidId,
  kidName,
  asset,
  currency,
  cashAvailable,
  backHref,
  existingHolding,
}: {
  kidId: string;
  kidName: string;
  asset: AssetDetailOut;
  currency: string;
  cashAvailable: number;
  backHref: string;
  existingHolding: HoldingOut | null;
}) {
  const { data: session } = useSession();
  const router = useRouter();

  // A "nice" starting quantity so the first thing a kid sees costs
  // something sensible — between 1 and 10 in the family's currency —
  // regardless of whether the stock is $5 or $2000. Mirrors the original
  // project's `_unit_step_for_price` (spec section 6).
  const step = useMemo(() => defaultUnitStep(Number(asset.price ?? 0)), [asset.price]);
  const stepDecimals = decimalsForStep(step);

  const [mode, setMode] = useState<Mode>("units");
  const [inputValue, setInputValue] = useState(() => String(step));
  const [quote, setQuote] = useState<BuySellQuoteResponse | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sellOpen, setSellOpen] = useState(false);

  const backendToken = session?.backendToken;

  useEffect(() => {
    // All state updates happen inside the timeout callback (not
    // synchronously in the effect body) — including the "clear" case —
    // so this stays a plain async subscription, not a synchronous setState.
    const timeout = setTimeout(async () => {
      const value = Number(inputValue);
      if (!backendToken || !value || value <= 0) {
        setQuote(null);
        return;
      }
      setQuoteLoading(true);
      setError(null);
      try {
        const body = mode === "amount" ? { symbol: asset.symbol, amount: value } : { symbol: asset.symbol, units: value };
        const q = await api.post<BuySellQuoteResponse>(`/kids/${kidId}/quote`, backendToken, body);
        setQuote(q);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Couldn't get a quote");
        setQuote(null);
      } finally {
        setQuoteLoading(false);
      }
    }, 300);
    return () => clearTimeout(timeout);
  }, [inputValue, mode, asset.symbol, kidId, backendToken]);

  const insufficientFunds = quote ? Number(quote.cost) > cashAvailable : false;
  const canBuy = quote && !insufficientFunds && !quoteLoading;

  function adjustUnits(direction: 1 | -1) {
    const current = Number(inputValue) || 0;
    const next = Math.max(step, current + direction * step);
    setInputValue(next.toFixed(stepDecimals));
  }

  async function handleBuy() {
    if (!session?.backendToken || !quote) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post<InvestmentTransactionOut>(`/kids/${kidId}/buy`, session.backendToken, {
        symbol: asset.symbol,
        units: quote.units,
      });
      router.push(`/home/kids/${kidId}`);
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  const sincePurchasePct = existingHolding ? formatPct(existingHolding.since_purchase_pct) : null;
  const sincePurchasePositive = Number(existingHolding?.since_purchase_pct ?? 0) >= 0;

  return (
    <div className="max-w-md mx-auto flex flex-col min-h-screen">
      <PageHeader title={`Buy ${asset.symbol}`} backHref={backHref} />

      <div className="px-5 pt-3.5">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="font-semibold text-[15px] text-emerald-dark">{asset.display_name}</div>
            <div className="text-[12.5px] text-muted">
              {formatUpdatedAt(asset.price_updated_at)}
              {asset.native_currency && ` · priced in ${currencySymbol(asset.native_currency)}`}
            </div>
          </div>
          {asset.price && (
            <div className="font-serif font-semibold text-[24px] text-emerald">
              {formatMoney(asset.price, currency)}
            </div>
          )}
        </div>

        {asset.description && (
          <p className="text-[13px] leading-relaxed text-muted-strong mt-2.5">{asset.description}</p>
        )}

        {asset.native_currency && <Sparkline history={asset.history} nativeCurrency={asset.native_currency} />}

        {existingHolding && (
          <div className="mt-3.5 bg-tint-icon rounded-[10px] px-3.5 py-3 flex items-center justify-between">
            <div className="text-[13px] font-medium text-muted-strong">
              You own {trimUnits(existingHolding.units)} units, worth{" "}
              {formatMoney(existingHolding.current_value, currency)}
              {sincePurchasePct && (
                <span className={sincePurchasePositive ? "text-positive" : "text-negative"}>
                  {" "}
                  ({sincePurchasePct} since bought)
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={() => setSellOpen(true)}
              className="text-[12.5px] font-semibold text-negative cursor-pointer shrink-0 ml-2"
            >
              Sell
            </button>
          </div>
        )}
      </div>

      <div className="flex-1 px-5 pt-5 pb-6 flex flex-col gap-4">
        <SegmentedControl
          value={mode}
          onChange={(m) => {
            setMode(m);
            setInputValue(m === "units" ? String(step) : "");
            setQuote(null);
          }}
          options={[
            { value: "units", label: "Units" },
            { value: "amount", label: `Amount (${currencySymbol(currency)})` },
          ]}
        />

        <div className="text-center py-[18px] bg-card border border-border-hairline rounded-2xl">
          {mode === "units" ? (
            <div className="flex items-center justify-center gap-4">
              <button
                type="button"
                aria-label="Fewer units"
                disabled={(Number(inputValue) || 0) <= step}
                onClick={() => adjustUnits(-1)}
                className="w-9 h-9 rounded-full bg-tint-emerald text-emerald text-[20px] font-bold flex items-center justify-center disabled:opacity-30 cursor-pointer"
              >
                −
              </button>
              <div className="inline-flex items-baseline gap-1.5 font-serif font-semibold text-[36px] text-emerald">
                <input
                  inputMode="decimal"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value.replace(/[^0-9.]/g, ""))}
                  placeholder="0"
                  className="bg-transparent outline-none w-28 text-center placeholder:text-emerald/30"
                />
                <span className="text-[15px] font-sans font-medium text-muted">units</span>
              </div>
              <button
                type="button"
                aria-label="More units"
                onClick={() => adjustUnits(1)}
                className="w-9 h-9 rounded-full bg-tint-emerald text-emerald text-[20px] font-bold flex items-center justify-center cursor-pointer"
              >
                +
              </button>
            </div>
          ) : (
            <div className="inline-flex items-baseline gap-0.5 font-serif font-semibold text-[36px] text-emerald">
              <span>{currencySymbol(currency)}</span>
              <input
                autoFocus
                inputMode="decimal"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value.replace(/[^0-9.]/g, ""))}
                placeholder="0.00"
                className="bg-transparent outline-none w-40 text-center placeholder:text-emerald/30"
              />
            </div>
          )}
          <div className="text-[13px] font-medium text-muted mt-1.5">
            {quoteLoading
              ? "calculating…"
              : quote
                ? mode === "units"
                  ? `≈ ${formatMoney(quote.cost, currency)}`
                  : // Amount mode snaps to the nearest real tradable step, so
                    // what's actually charged can differ from what was typed
                    // (e.g. "€3" might really cost €3.19) — show both.
                    `≈ ${trimUnits(quote.units)} units of ${asset.symbol} · costs ${formatMoney(quote.cost, currency)}`
                : "enter an amount to see the cost"}
          </div>
        </div>

        <div className="bg-tint-emerald rounded-[10px] px-3.5 py-3 text-[12.5px] leading-relaxed text-tint-dark">
          Virtual money, real price. {kidName} isn&apos;t buying real {asset.display_name} — this just
          tracks what their balance would be worth if they had.
        </div>

        <div className="flex justify-between text-[14px] font-medium text-muted">
          <span>Cash available after</span>
          <span className="font-bold text-emerald">
            {formatMoney(cashAvailable - Number(quote?.cost ?? 0), currency)}
          </span>
        </div>

        {insufficientFunds && (
          <p className="text-[13px] text-negative -mt-2">Not enough cash available for this purchase.</p>
        )}
        {error && <p className="text-[13px] text-negative -mt-2">{error}</p>}

        <button
          type="button"
          disabled={!canBuy || submitting}
          onClick={handleBuy}
          className="bg-emerald text-white text-center py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
        >
          {submitting ? "Buying…" : `Buy for ${formatMoney(quote?.cost ?? 0, currency)}`}
        </button>
      </div>

      {sellOpen && existingHolding && (
        <SellSheet
          onClose={() => setSellOpen(false)}
          kidId={kidId}
          holding={existingHolding}
          cashAvailable={cashAvailable}
          currency={currency}
        />
      )}
    </div>
  );
}
