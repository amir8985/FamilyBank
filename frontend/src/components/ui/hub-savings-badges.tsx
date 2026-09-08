"use client";

import { useState } from "react";

type Kind = "flexible" | "locked";

/** Brass "Deactivated" pill for a kind with plans but none switched on —
 * tap for a one-liner. */
export function HubDeactivatedBadge({ kind }: { kind: Kind }) {
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
        Deactivated
      </button>
      {open && (
        <span className="text-[11.5px] text-brass-dark leading-relaxed bg-tint-brass/50 rounded-lg px-2.5 py-1.5">
          No {kind} plan is switched on, so your kid can&apos;t start a new {kind} deposit until you
          turn one on in the settings.
        </span>
      )}
    </span>
  );
}

/** Red "N still growing" pill for leftover deposits sitting in a
 * switched-off plan — tap for the detail. Redder than "Deactivated"
 * because there's real money involved. */
export function HubStillGrowingBadge({ count, kind }: { count: number; kind: Kind }) {
  const [open, setOpen] = useState(false);
  const noun = count === 1 ? "deposit" : "deposits";
  const them = count === 1 ? "it" : "them";
  return (
    <span className="flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          setOpen((v) => !v);
        }}
        className="text-[10px] font-semibold text-negative bg-tint-negative rounded-full px-1.5 py-0.5 cursor-pointer"
      >
        {count} still growing
      </button>
      {open && (
        <span className="text-[11.5px] text-negative leading-relaxed bg-tint-negative/60 rounded-lg px-2.5 py-1.5">
          {count} {noun} from before {count === 1 ? "is" : "are"} still earning interest in a
          switched-off plan. Cash {them} out from the plan in settings, or your kid can withdraw{" "}
          {them} from their savings screen{kind === "locked" ? " once the lock term is up" : " any time"}.
        </span>
      )}
    </span>
  );
}
