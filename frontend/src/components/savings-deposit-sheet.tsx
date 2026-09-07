"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { api, ApiError } from "@/lib/api";
import { currencySymbol, formatMoney } from "@/lib/format";
import type { DepositablePlanOut } from "@/lib/types";

function maturityDate(lockMonths: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() + lockMonths);
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
}

export function SavingsDepositSheet({
  kidId,
  plan,
  cashAvailable,
  currency,
  onClose,
}: {
  kidId: string;
  plan: DepositablePlanOut;
  cashAvailable: number;
  currency: string;
  onClose: () => void;
}) {
  const { data: session } = useSession();
  const router = useRouter();
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsed = Number(amount) || 0;
  const tooMuch = parsed > cashAvailable;
  const locked = plan.lock_months > 0;

  async function handleConfirm() {
    if (!session?.backendToken || parsed <= 0 || tooMuch) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/kids/${kidId}/savings/deposit`, session.backendToken, {
        plan_id: plan.id,
        amount: parsed,
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
        Put money into {plan.name}
      </h2>

      <p className="text-[13px] text-muted leading-relaxed -mt-2">
        {Number(plan.monthly_rate).toFixed(1)}%/month (≈ {Number(plan.annual_rate).toFixed(1)}%/year).{" "}
        {locked
          ? `Locked until about ${maturityDate(plan.lock_months)} — you can't take it out before then.`
          : "Withdraw it whenever you like."}
      </p>

      <div className="text-center py-[18px] bg-cream rounded-2xl">
        <div className="inline-flex items-baseline gap-0.5 font-serif font-semibold text-[40px] text-emerald">
          <span className="font-sans">{currencySymbol(currency)}</span>
          <input
            autoFocus
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ""))}
            placeholder="0.00"
            className="bg-transparent outline-none w-40 text-center placeholder:text-emerald/30"
          />
        </div>
      </div>

      <div className="flex justify-between text-[14px] font-medium text-muted px-0.5">
        <span>Cash available</span>
        <span className="font-bold text-emerald">{formatMoney(cashAvailable, currency)}</span>
      </div>

      {tooMuch && <p className="text-[13px] text-negative -mt-2">That&apos;s more than the cash available.</p>}
      {error && <p className="text-[13px] text-negative -mt-2">{error}</p>}

      <button
        type="button"
        disabled={submitting || parsed <= 0 || tooMuch}
        onClick={handleConfirm}
        className="bg-emerald text-white text-center min-h-11 py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        {submitting ? "Saving…" : `Move ${formatMoney(parsed, currency)} to savings`}
      </button>
    </BottomSheet>
  );
}
