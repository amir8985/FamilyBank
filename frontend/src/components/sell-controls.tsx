"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { Money } from "@/components/ui/money";
import { api, ApiError } from "@/lib/api";
import { defaultUnitStep, formatMoney, trimUnits } from "@/lib/format";
import type { HoldingOut, InvestmentTransactionOut } from "@/lib/types";

function decimalsForStep(step: number): number {
  if (step >= 1) return 0;
  return Math.round(-Math.log10(step));
}

// The actual "how many units, for how much" picker — shared by SellSheet
// (wrapped in a BottomSheet, for the Buy screen's "you own this" banner)
// and lot-detail-client.tsx (rendered directly inline, no popup, per the
// user's explicit request that an owned position's sell UI shouldn't
// need a separate window).
export function SellControls({
  kidId,
  holding,
  cashAvailable,
  currency,
  onSold,
}: {
  kidId: string;
  holding: HoldingOut;
  cashAvailable: number;
  currency: string;
  onSold: () => void;
}) {
  const { data: session } = useSession();

  const totalUnits = Number(holding.units);
  const pricePerUnit = totalUnits > 0 ? Number(holding.current_value) / totalUnits : 0;
  const step = defaultUnitStep(pricePerUnit);
  const stepDecimals = decimalsForStep(step);

  const [unitsStr, setUnitsStr] = useState(() => trimUnits(holding.units));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // A partial sell doesn't unmount this component — the parent just
  // passes a smaller `holding.units` after its `router.refresh()`. Reset
  // the picker to the new max whenever that happens (adjusting state
  // during render, React's recommended pattern for this — see
  // https://react.dev/learn/you-might-not-need-an-effect — rather than
  // a useEffect, which the lint rule here flags), or the stepper gets
  // stuck at the pre-sell amount (larger than what's left) with both
  // +/- disabled and the confirm button silently clamped to a
  // stale-looking number.
  const [lastSeenUnits, setLastSeenUnits] = useState(holding.units);
  if (holding.units !== lastSeenUnits) {
    setLastSeenUnits(holding.units);
    setUnitsStr(trimUnits(holding.units));
  }

  const units = Math.min(Number(unitsStr) || 0, totalUnits);
  const proceeds = units * pricePerUnit;
  const valid = units > 0 && units <= totalUnits;
  const isFullSell = valid && units === totalUnits;

  function adjust(direction: 1 | -1) {
    const current = Number(unitsStr) || 0;
    const next = Math.min(totalUnits, Math.max(step, current + direction * step));
    setUnitsStr(next.toFixed(stepDecimals));
  }

  async function handleConfirm() {
    if (!session?.backendToken || !valid) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post<InvestmentTransactionOut>(`/kids/${kidId}/sell`, session.backendToken, {
        ...(holding.lot_id ? { lot_id: holding.lot_id } : { symbol: holding.symbol }),
        units,
      });
      onSold();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <span className="text-[12px] font-semibold text-muted">Units to sell</span>
        <div className="flex items-center justify-center gap-4 py-2">
          <button
            type="button"
            aria-label="Fewer units"
            disabled={units <= step}
            onClick={() => adjust(-1)}
            className="w-11 h-11 rounded-full bg-tint-emerald text-emerald text-[20px] font-bold flex items-center justify-center disabled:opacity-30 cursor-pointer"
          >
            −
          </button>
          <input
            inputMode="decimal"
            value={unitsStr}
            onChange={(e) => setUnitsStr(e.target.value.replace(/[^0-9.]/g, ""))}
            className="w-28 text-center font-serif font-semibold text-[28px] text-emerald bg-transparent outline-none border-b border-border-hairline-strong focus:border-emerald"
          />
          <button
            type="button"
            aria-label="More units"
            disabled={units >= totalUnits}
            onClick={() => adjust(1)}
            className="w-11 h-11 rounded-full bg-tint-emerald text-emerald text-[20px] font-bold flex items-center justify-center disabled:opacity-30 cursor-pointer"
          >
            +
          </button>
        </div>
        <button
          type="button"
          onClick={() => setUnitsStr(trimUnits(holding.units))}
          className="self-center text-[12.5px] font-semibold text-emerald cursor-pointer"
        >
          Max
        </button>
      </div>

      <div className="text-center py-[18px] bg-cream rounded-2xl">
        <div className="font-serif font-semibold text-[32px] text-emerald">
          <Money amount={proceeds} currency={currency} />
        </div>
        <div className="text-[13px] font-medium text-muted mt-1">estimated proceeds</div>
      </div>

      <div className="flex justify-between text-[14px] font-medium text-muted px-0.5">
        <span>Cash available after</span>
        <span className="font-bold text-emerald">{formatMoney(cashAvailable + proceeds, currency)}</span>
      </div>

      {error && <p className="text-[13px] text-negative -mt-2">{error}</p>}

      <button
        type="button"
        disabled={submitting || !valid}
        onClick={handleConfirm}
        className="bg-negative text-white text-center min-h-11 py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        {submitting
          ? "Selling…"
          : isFullSell
            ? `Sell all for ${formatMoney(proceeds, currency)}`
            : `Sell for ${formatMoney(proceeds, currency)}`}
      </button>
    </div>
  );
}
