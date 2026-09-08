"use client";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { formatMoney } from "@/lib/format";
import type { PlanDepositOut, SavingsPlanOut } from "@/lib/types";

export type AffectedPlan = { plan: SavingsPlanOut; deposits: PlanDepositOut[] };

// Shown on Save when the parent is switching off a plan a kid still has
// money in. Amber, not red — nothing bad happens either way, it's just a
// fork: cash the kids out now, or leave their deposits running.
export function SavingsChangesSheet({
  affected,
  working,
  onCashOutAndSave,
  onJustSave,
  onClose,
}: {
  affected: AffectedPlan[];
  working: boolean;
  onCashOutAndSave: () => void;
  onJustSave: () => void;
  onClose: () => void;
}) {
  const depositCount = affected.reduce((n, a) => n + a.deposits.length, 0);
  const kidNames = [...new Set(affected.flatMap((a) => a.deposits.map((d) => d.kid_name)))];

  return (
    <BottomSheet onClose={onClose}>
      <div className="flex items-center gap-2">
        <span className="text-[19px]" aria-hidden>
          🟠
        </span>
        <h2 className="font-serif font-semibold text-[19px] text-brass-dark">
          {depositCount} deposit{depositCount === 1 ? "" : "s"} still in{" "}
          {affected.length === 1 ? "this plan" : "these plans"}
        </h2>
      </div>

      <div className="bg-tint-brass rounded-2xl px-4 py-3.5 flex flex-col gap-3 text-brass-dark">
        <p className="text-[13px] leading-relaxed">
          Switching {affected.length === 1 ? "it" : "them"} off just stops new deposits.{" "}
          {kidNames.length === 1 ? `${kidNames[0]}'s` : `${kidNames.length} kids'`} money keeps
          growing at the same rate unless you cash it out.
        </p>
        <div className="flex flex-col gap-2">
          {affected.map(({ plan, deposits }) => (
            <div key={plan.id} className="flex flex-col gap-0.5">
              <span className="text-[12px] font-semibold">{plan.name}</span>
              {deposits.map((d) => (
                <span key={d.kid_id} className="text-[12.5px] flex justify-between">
                  <span>
                    {d.kid_name}
                    {d.is_locked ? " · locked" : ""}
                  </span>
                  <span className="font-semibold">{formatMoney(d.current_value, d.currency)}</span>
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>

      <button
        type="button"
        disabled={working}
        onClick={onCashOutAndSave}
        className="bg-brass-dark text-white text-center min-h-11 py-[14px] rounded-xl text-[14.5px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        {working ? "Working…" : "Cash out & turn off"}
      </button>
      <button
        type="button"
        disabled={working}
        onClick={onJustSave}
        className="text-center min-h-11 py-[12px] rounded-xl text-[13.5px] font-semibold border border-brass-dark text-brass-dark disabled:opacity-50 cursor-pointer"
      >
        Turn off, keep the savings
      </button>
      <button
        type="button"
        onClick={onClose}
        disabled={working}
        className="text-center py-1.5 text-muted font-semibold text-[13px] cursor-pointer disabled:opacity-50"
      >
        Cancel
      </button>
    </BottomSheet>
  );
}
