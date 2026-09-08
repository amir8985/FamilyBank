"use client";

import { useState } from "react";

/** Orange marker for a savings plan that's switched off for new deposits
 * but still has a kid's money in it, quietly compounding. Tap to reveal
 * a one-line explanation — same tap-to-reveal pattern as the boost
 * badge. */
export function StillGrowingBadge({ count, rate }: { count: number; rate: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="inline-flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-[10px] font-semibold text-brass-dark bg-tint-brass rounded-full px-1.5 py-0.5 cursor-pointer"
      >
        {count} still saving
      </button>
      {open && (
        <span className="text-[11.5px] text-brass-dark leading-relaxed bg-tint-brass/50 rounded-lg px-2.5 py-1.5 max-w-[280px]">
          This plan is off, so no new money can go in — but {count} deposit
          {count === 1 ? "" : "s"} already in it keep{count === 1 ? "s" : ""} earning{" "}
          {Number(rate).toFixed(1)}%/month until withdrawn or cashed out.
        </span>
      )}
    </span>
  );
}
