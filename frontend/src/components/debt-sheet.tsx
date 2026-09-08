"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { useFamily } from "@/lib/family-store";
import { invalidateKid } from "@/lib/use-cached-resource";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { currencySymbol, formatMoney } from "@/lib/format";
import type { DebtTransactionType, DebtUpdateResult } from "@/lib/types";

// Caller mounts this only while the sheet should be visible (see
// home-client.tsx), so each open is a fresh mount — no reset effect needed.
export function DebtSheet({
  onClose,
  kidId,
  kidName,
  currentBalance,
  currency,
  initialDirection,
}: {
  onClose: () => void;
  kidId: string;
  kidName: string;
  currentBalance: number;
  currency: string;
  initialDirection: DebtTransactionType;
}) {
  const { data: session } = useSession();
  const { applyKidBalanceDelta, refreshHome } = useFamily();
  const toast = useToast();
  const [direction, setDirection] = useState<DebtTransactionType>(initialDirection);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const parsedAmount = Number(amount) || 0;
  const newBalance =
    direction === "add" ? currentBalance + parsedAmount : currentBalance - parsedAmount;

  function handleConfirm() {
    if (!session?.backendToken || parsedAmount <= 0 || submitting) return;
    setSubmitting(true);

    const token = session.backendToken;
    const delta = direction === "add" ? parsedAmount : -parsedAmount;
    const trimmedNote = note.trim() || null;

    // Apply immediately and close — the parent already has everything it
    // needs to show the result. Persistence and reconciliation happen in
    // the background; a failure rolls the balance back and explains why.
    const rollback = applyKidBalanceDelta(kidId, delta);
    onClose();

    api
      .post<DebtUpdateResult>(`/kids/${kidId}/debt`, token, {
        type: direction,
        amount: parsedAmount,
        note: trimmedNote,
      })
      .then(() => {
        invalidateKid(kidId);
        return refreshHome();
      })
      .catch((e) => {
        rollback();
        const msg =
          e instanceof ApiError && e.status < 500
            ? e.message
            : `Couldn't update ${kidName}'s balance — it's been restored.`;
        toast(msg, "error");
      });
  }

  return (
    <BottomSheet onClose={onClose}>
      <h2 className="font-serif font-semibold text-[20px] text-emerald-dark">
        Update {kidName}&apos;s balance
      </h2>

      <SegmentedControl
        variant="filled"
        value={direction}
        onChange={setDirection}
        options={[
          { value: "add", label: "Add" },
          { value: "deduct", label: "Deduct", activeClassName: "bg-negative text-white" },
        ]}
      />

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

      <label className="flex flex-col gap-1.5">
        <span className="text-[12px] font-semibold text-muted">Note (optional)</span>
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="For Wednesday chores"
          maxLength={280}
          className="border border-border-hairline-strong rounded-[10px] px-3.5 py-3 text-[14.5px] text-emerald-dark outline-none focus:border-emerald"
        />
      </label>

      <div className="flex justify-between text-[14px] font-medium text-muted px-0.5">
        <span>New balance</span>
        <span className="font-bold text-emerald">{formatMoney(newBalance, currency)}</span>
      </div>

      <button
        type="button"
        disabled={submitting || parsedAmount <= 0}
        onClick={handleConfirm}
        className="bg-emerald text-white text-center min-h-11 py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        Confirm
      </button>
    </BottomSheet>
  );
}
