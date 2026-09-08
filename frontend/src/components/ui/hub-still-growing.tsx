"use client";

import { useState } from "react";

/** The hub card's orange "Savings still growing" pill — tap to reveal a
 * one-liner. In this state (no plan of this kind switched on) there's no
 * way to redeem the leftover deposits from Settings — that's the kid's
 * move from their own savings screen, and a locked one only once its
 * term is up. */
export function HubStillGrowingBadge({ count, kind }: { count: number; kind: "flexible" | "locked" }) {
  const [open, setOpen] = useState(false);
  const noun = count === 1 ? "deposit" : "deposits";
  return (
    <span className="flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          setOpen((v) => !v);
        }}
        className="text-[10px] font-semibold text-brass-dark bg-tint-brass rounded-full px-1.5 py-0.5 cursor-pointer"
      >
        Savings still growing
      </button>
      {open && (
        <span className="text-[11.5px] text-brass-dark leading-relaxed bg-tint-brass/50 rounded-lg px-2.5 py-1.5">
          No {kind} plan is switched on for new deposits, but {count} {noun} from before{" "}
          {count === 1 ? "is" : "are"} still earning interest.{" "}
          {kind === "locked"
            ? `Your kid can withdraw ${count === 1 ? "it" : "them"} from their savings screen once the lock term is up.`
            : `Your kid can withdraw ${count === 1 ? "it" : "them"} any time from their savings screen.`}
        </span>
      )}
    </span>
  );
}
