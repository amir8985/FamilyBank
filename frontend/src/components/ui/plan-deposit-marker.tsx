"use client";

import { useState } from "react";

/** Small marker on a savings-plan card showing how many open deposits
 * ("pots") it holds.
 *  - active plan  → plain emerald count pill.
 *  - switched-off plan that still holds money → orange, tap to reveal a
 *    one-liner. A parent can force it closed with the card's Cash out
 *    button; otherwise the kid withdraws it from their own savings
 *    screen (a locked one only once its term is up). */
export function PlanDepositMarker({
  count,
  active,
  locked,
  rate,
}: {
  count: number;
  active: boolean;
  locked: boolean;
  rate: string;
}) {
  const [open, setOpen] = useState(false);
  const noun = count === 1 ? "deposit" : "deposits";
  const them = count === 1 ? "it" : "them";

  if (active) {
    return (
      <span className="self-start text-[10px] font-semibold text-tint-dark bg-tint-emerald rounded-full px-1.5 py-0.5">
        {count} {noun}
      </span>
    );
  }

  return (
    <span className="flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-[10px] font-semibold text-brass-dark bg-tint-brass rounded-full px-1.5 py-0.5 cursor-pointer"
      >
        {count} still saving
      </button>
      {open && (
        <span className="text-[11.5px] text-brass-dark leading-relaxed bg-tint-brass/50 rounded-lg px-2.5 py-1.5 max-w-[280px]">
          This plan is off, so no new money can go in — but {count} {noun} already in it{" "}
          {count === 1 ? "keeps" : "keep"} earning {Number(rate).toFixed(1)}%/month. Cash {them} out
          with the button, or your kid can withdraw {them} from their savings screen
          {locked ? " once the lock term is up" : " any time"}.
        </span>
      )}
    </span>
  );
}
