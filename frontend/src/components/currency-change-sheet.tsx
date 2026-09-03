"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { api, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { CurrencyChangePreviewOut } from "@/lib/types";

// Mounted only while the parent has picked a *different* currency than
// the family's current one — see settings-form.tsx. Currency change is
// rare and rewrites every kid's balance at today's exchange rate, so
// this always shows the real converted numbers before anything commits,
// rather than a generic "are you sure?".
export function CurrencyChangeSheet({
  fromCurrency,
  toCurrency,
  onClose,
}: {
  fromCurrency: string;
  toCurrency: string;
  onClose: () => void;
}) {
  const { data: session } = useSession();
  const router = useRouter();
  const [preview, setPreview] = useState<CurrencyChangePreviewOut | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  useEffect(() => {
    if (!session?.backendToken) return;
    let cancelled = false;
    api
      .get<CurrencyChangePreviewOut>(
        `/family/settings/currency-preview?to=${toCurrency}`,
        session.backendToken
      )
      .then((data) => {
        if (!cancelled) setPreview(data);
      })
      .catch((e) => {
        if (!cancelled) setLoadError(e instanceof ApiError ? e.message : "Something went wrong");
      });
    return () => {
      cancelled = true;
    };
  }, [session?.backendToken, toCurrency]);

  async function handleConfirm() {
    if (!session?.backendToken) return;
    setConfirming(true);
    setConfirmError(null);
    try {
      await api.patch("/family/settings", session.backendToken, { base_currency: toCurrency });
      onClose();
      router.refresh();
    } catch (e) {
      setConfirmError(e instanceof ApiError ? e.message : "Something went wrong");
      setConfirming(false);
    }
  }

  return (
    <BottomSheet onClose={onClose}>
      <h2 className="font-serif font-semibold text-[20px] text-emerald-dark">
        Change currency to {toCurrency}?
      </h2>

      <p className="text-[13.5px] text-muted leading-relaxed">
        This is a big change most families never need to make. Every kid&apos;s balance and
        investment value will be converted from {fromCurrency} to {toCurrency} at today&apos;s
        exchange rate — nothing is lost, but the numbers everyone sees will change immediately.
      </p>

      {loadError && <p className="text-[13px] text-negative">{loadError}</p>}

      {!preview && !loadError && (
        <p className="text-[13px] text-muted text-center py-2">Calculating conversion…</p>
      )}

      {preview && (
        <div className="flex flex-col gap-2">
          {preview.kids.map((k) => (
            <div
              key={k.kid_id}
              className="bg-cream rounded-2xl px-4 py-3 flex items-center justify-between"
            >
              <span className="font-semibold text-[14px] text-emerald-dark">{k.name}</span>
              <span className="text-[13.5px] text-muted">
                {formatMoney(k.old_cash_balance, fromCurrency)}
                {" → "}
                <span className="font-semibold text-emerald-dark">
                  {formatMoney(k.new_cash_balance, toCurrency)}
                </span>
              </span>
            </div>
          ))}
          {preview.kids.length === 0 && (
            <p className="text-[13px] text-muted text-center py-1">No kids yet — nothing to convert.</p>
          )}
        </div>
      )}

      {confirmError && <p className="text-[13px] text-negative">{confirmError}</p>}

      <button
        type="button"
        disabled={!preview || confirming}
        onClick={handleConfirm}
        className="bg-emerald text-white text-center py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        {confirming ? "Changing currency…" : `Yes, convert everything to ${toCurrency}`}
      </button>
      <button
        type="button"
        onClick={onClose}
        className="text-center py-2 text-muted font-semibold text-[13.5px] cursor-pointer"
      >
        Cancel
      </button>
    </BottomSheet>
  );
}
