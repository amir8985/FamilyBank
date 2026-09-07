"use client";

// Shared by the lot detail page (an existing purchase) and the Buy
// screen (a prospective one — "buying this now will be boosted at this
// rate") — same wording works for both since it doesn't say "was" or
// "will be", just what boosted purchases do.
export function BoostedBadge({ rate, onToggle }: { rate: string; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="text-[10px] font-semibold text-tint-dark bg-tint-emerald rounded-full px-1.5 py-0.5 cursor-pointer"
    >
      Boosted {rate}%/mo
    </button>
  );
}

export function BoostedExplanation({ rate }: { rate: string }) {
  return (
    <p className="text-[12px] text-muted leading-relaxed bg-tint-emerald/40 rounded-xl px-3 py-2.5">
      Boosted purchases earn an extra {rate}% a month on top of real gains — only on days the
      price rises, never subtracted on a day it falls.
    </p>
  );
}
