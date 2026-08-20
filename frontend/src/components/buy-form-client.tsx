"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Sparkline } from "@/components/ui/sparkline";
import { PageHeader } from "@/components/ui/page-header";
import { api, ApiError } from "@/lib/api";
import { currencySymbol, formatMoney, formatUnits } from "@/lib/format";
import type { AssetDetailOut, BuySellQuoteResponse, InvestmentTransactionOut } from "@/lib/types";

type Mode = "amount" | "units";

export function BuyFormClient({
  kidId,
  kidName,
  asset,
  currency,
  cashAvailable,
}: {
  kidId: string;
  kidName: string;
  asset: AssetDetailOut;
  currency: string;
  cashAvailable: number;
}) {
  const { data: session } = useSession();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("amount");
  const [inputValue, setInputValue] = useState("");
  const [quote, setQuote] = useState<BuySellQuoteResponse | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

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

  return (
    <div className="max-w-md mx-auto flex flex-col min-h-screen">
      <PageHeader title={`Buy ${asset.symbol}`} backHref={`/home/kids/${kidId}`} />

      <div className="px-5 pt-3.5">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="font-semibold text-[15px] text-emerald-dark">{asset.display_name}</div>
            {asset.native_currency && (
              <div className="text-[12.5px] text-muted">
                live price, in {currencySymbol(asset.native_currency)}
              </div>
            )}
          </div>
          {asset.price && (
            <div className="font-serif font-semibold text-[24px] text-emerald">
              {formatMoney(asset.price, currency)}
            </div>
          )}
        </div>
        <Sparkline history={asset.history} />
      </div>

      <div className="flex-1 px-5 pt-5 pb-6 flex flex-col gap-4">
        <SegmentedControl
          value={mode}
          onChange={(m) => {
            setMode(m);
            setInputValue("");
            setQuote(null);
          }}
          options={[
            { value: "amount", label: `Amount (${currencySymbol(currency)})` },
            { value: "units", label: "Units" },
          ]}
        />

        <div className="text-center py-[18px] bg-card border border-border-hairline rounded-2xl">
          {mode === "amount" ? (
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
          ) : (
            <div className="inline-flex items-baseline gap-1 font-serif font-semibold text-[36px] text-emerald">
              <input
                autoFocus
                inputMode="decimal"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value.replace(/[^0-9.]/g, ""))}
                placeholder="0"
                className="bg-transparent outline-none w-32 text-center placeholder:text-emerald/30"
              />
              <span className="text-[15px] font-sans font-medium text-muted">units</span>
            </div>
          )}
          <div className="text-[13px] font-medium text-muted mt-1">
            {quoteLoading
              ? "calculating…"
              : quote
                ? mode === "amount"
                  ? `≈ ${formatUnits(quote.units)} units of ${asset.symbol}`
                  : `≈ ${formatMoney(quote.cost, currency)}`
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
    </div>
  );
}
