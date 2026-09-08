"use client";

import { useState } from "react";

/** The hub card's orange "Savings still growing" pill — tap to reveal a
 * one-liner, same idea as StillGrowingBadge on the settings page. */
export function HubStillGrowingBadge({ count, kind }: { count: number; kind: "flexible" | "locked" }) {
  const [open, setOpen] = useState(false);
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
          No {kind} plan is switched on for new deposits, but {count} deposit{count === 1 ? "" : "s"}{" "}
          from before {count === 1 ? "is" : "are"} still earning interest. Open the settings to cash{" "}
          {count === 1 ? "it" : "them"} out or switch a plan back on.
        </span>
      )}
    </span>
  );
}
