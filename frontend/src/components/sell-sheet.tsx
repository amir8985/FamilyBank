"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { api, ApiError } from "@/lib/api";
import { defaultUnitStep, formatMoney, trimUnits } from "@/lib/format";
import type { HoldingOut, InvestmentTransactionOut } from "@/lib/types";

function decimalsForStep(step: number): number {
  if (step >= 1) return 0;
  return Math.round(-Math.log10(step));
}

// Caller mounts this only while the sheet should be visible (see
// portfolio-client.tsx), so each open is a fresh mount — no reset effect needed.
export function SellSheet({
  onClose,
  kidId,
  holding,
  cashAvailable,
  currency,
}: {
  onClose: () => void;
  kidId: string;
  holding: HoldingOut;
  cashAvailable: number;
  currency: string;
}) {
  const { data: session } = useSession();
  const router = useRouter();

  const totalUnits = Number(holding.units);
  const pricePerUnit = totalUnits > 0 ? Number(holding.current_value) / totalUnits : 0;
  const step = defaultUnitStep(pricePerUnit);
  const stepDecimals = decimalsForStep(step);

  const [unitsStr, setUnitsStr] = useState(() => trimUnits(holding.units));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const units = Math.min(Number(unitsStr) || 0, totalUnits);
  const proceeds = units * pricePerUnit;
  const valid = units > 0 && units <= totalUnits;

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
        symbol: holding.symbol,
        units,
      });
      onClose();
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <BottomSheet onClose={onClose}>
      <h2 className="font-serif font-semibold text-[20px] text-emerald-dark">
        Sell {holding.display_name}
      </h2>
      <p className="text-[12.5px] text-muted -mt-3">
        You hold {trimUnits(holding.units)} units, worth {formatMoney(holding.current_value, currency)}.
      </p>

      <div className="flex flex-col gap-1.5">
        <span className="text-[12px] font-semibold text-muted">Units to sell</span>
        <div className="flex items-center justify-center gap-4 py-2">
          <button
            type="button"
            aria-label="Fewer units"
            disabled={units <= step}
            onClick={() => adjust(-1)}
            className="w-9 h-9 rounded-full bg-tint-emerald text-emerald text-[20px] font-bold flex items-center justify-center disabled:opacity-30 cursor-pointer"
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
            className="w-9 h-9 rounded-full bg-tint-emerald text-emerald text-[20px] font-bold flex items-center justify-center disabled:opacity-30 cursor-pointer"
          >
            +
          </button>
        </div>
        <button
          type="button"
          onClick={() => setUnitsStr(trimUnits(holding.units))}
          className="self-center text-[12.5px] font-semibold text-emerald cursor-pointer"
        >
          Sell all
        </button>
      </div>

      <div className="text-center py-[18px] bg-cream rounded-2xl">
        <div className="font-serif font-semibold text-[32px] text-emerald">
          {formatMoney(proceeds, currency)}
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
        className="bg-emerald text-white text-center py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        {submitting ? "Selling…" : `Sell for ${formatMoney(proceeds, currency)}`}
      </button>
    </BottomSheet>
  );
}
