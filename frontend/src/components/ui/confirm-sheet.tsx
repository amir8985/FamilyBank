"use client";

import { BottomSheet } from "@/components/ui/bottom-sheet";

/** Amber-toned confirmation sheet — our in-app replacement for a bare
 * browser confirm() on savings actions that shuffle real balances
 * around (deleting a plan, cashing a plan's deposits out). Deliberately
 * calmer than SellAndRebuySheet's red: this is an "are you sure" nudge,
 * not a warning. */
export function ConfirmSheet({
  title,
  body,
  confirmLabel,
  confirming,
  onConfirm,
  onClose,
}: {
  title: string;
  body: React.ReactNode;
  confirmLabel: string;
  confirming: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <BottomSheet onClose={onClose}>
      <div className="flex items-center gap-2">
        <span className="text-[19px]" aria-hidden>
          🟠
        </span>
        <h2 className="font-serif font-semibold text-[19px] text-brass-dark">{title}</h2>
      </div>

      <div className="bg-tint-brass rounded-2xl px-4 py-3.5 text-[13.5px] text-brass-dark leading-relaxed">
        {body}
      </div>

      <button
        type="button"
        disabled={confirming}
        onClick={onConfirm}
        className="bg-brass-dark text-white text-center min-h-11 py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        {confirming ? "Working…" : confirmLabel}
      </button>
      <button
        type="button"
        onClick={onClose}
        disabled={confirming}
        className="text-center py-2 text-muted font-semibold text-[13.5px] cursor-pointer disabled:opacity-50"
      >
        Cancel
      </button>
    </BottomSheet>
  );
}
