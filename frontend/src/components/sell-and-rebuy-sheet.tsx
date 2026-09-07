"use client";

import { BottomSheet } from "@/components/ui/bottom-sheet";

// A deliberately loud, red-toned confirmation — this is the one action
// in this feature the user specifically asked not to be a bare browser
// confirm(), since it silently sells and rebuys every kid's entire
// portfolio at once (see boost-settings-form.tsx).
export function SellAndRebuySheet({
  targetLabel,
  confirming,
  onConfirm,
  onClose,
}: {
  targetLabel: string;
  confirming: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <BottomSheet onClose={onClose}>
      <div className="flex items-center gap-2">
        <span className="text-[20px]" aria-hidden>
          ⚠️
        </span>
        <h2 className="font-serif font-semibold text-[19px] text-negative">Sell everything and rebuy?</h2>
      </div>

      <div className="bg-tint-negative rounded-2xl px-4 py-3.5 flex flex-col gap-2.5">
        <p className="text-[13.5px] text-negative leading-relaxed">
          Here&apos;s exactly what happens, right now, for every kid in the family:
        </p>
        <ol className="text-[13.5px] text-negative leading-relaxed list-decimal pl-4 flex flex-col gap-1">
          <li>Every stock every kid owns gets sold, at today&apos;s price.</li>
          <li>
            The boost switches to <strong>{targetLabel}</strong>.
          </li>
          <li>The exact same stocks get bought right back, now locked in at the new setting.</li>
        </ol>
        <p className="text-[12px] text-negative/75 leading-relaxed">
          Cash balances should land back about where they started — this is really just how an
          already-owned position&apos;s rate gets changed, since a purchase locks in its rate for
          as long as it&apos;s held.
        </p>
      </div>

      <button
        type="button"
        disabled={confirming}
        onClick={onConfirm}
        className="bg-negative text-white text-center min-h-11 py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        {confirming ? "Selling and rebuying…" : "Yes, sell everything and rebuy"}
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
