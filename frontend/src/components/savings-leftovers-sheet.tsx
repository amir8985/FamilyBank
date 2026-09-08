"use client";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { formatMoney } from "@/lib/format";
import type { PlanDepositOut, SavingsPlanOut } from "@/lib/types";

export type LeftoverPlan = { plan: SavingsPlanOut; deposits: PlanDepositOut[] };

// Shown right AFTER a save that leaves a switched-off plan with a kid's
// money still in it. Amber, informational — offers the two ways to
// resolve each one: cash it out, or switch the plan back on.
export function SavingsLeftoversSheet({
  leftovers,
  busyId,
  onCashOut,
  onReopen,
  onClose,
}: {
  leftovers: LeftoverPlan[];
  busyId: string | null;
  onCashOut: (plan: SavingsPlanOut) => void;
  onReopen: (plan: SavingsPlanOut) => void;
  onClose: () => void;
}) {
  return (
    <BottomSheet onClose={onClose}>
      <div className="flex items-center gap-2">
        <span className="text-[19px]" aria-hidden>
          🟠
        </span>
        <h2 className="font-serif font-semibold text-[19px] text-brass-dark">
          Savings still in switched-off plan{leftovers.length === 1 ? "" : "s"}
        </h2>
      </div>

      <p className="text-[13px] text-muted leading-relaxed -mt-1">
        No new money can go into {leftovers.length === 1 ? "this plan" : "these plans"}, but what&apos;s
        already in {leftovers.length === 1 ? "it keeps" : "them keeps"} earning interest. Cash it out,
        or switch the plan back on.
      </p>

      <div className="flex flex-col gap-3">
        {leftovers.map(({ plan, deposits }) => (
          <div key={plan.id} className="bg-tint-brass rounded-2xl px-4 py-3.5 flex flex-col gap-2 text-brass-dark">
            <span className="text-[13px] font-semibold">{plan.name}</span>
            <div className="flex flex-col gap-0.5">
              {deposits.map((d) => (
                <span key={d.kid_id} className="text-[12.5px] flex justify-between">
                  <span>
                    {d.kid_name}
                    {d.is_locked && !d.is_matured ? " · locked" : ""}
                  </span>
                  <span className="font-semibold">{formatMoney(d.current_value, d.currency)}</span>
                </span>
              ))}
            </div>
            <div className="flex gap-2 pt-0.5">
              <button
                type="button"
                disabled={busyId === plan.id}
                onClick={() => onCashOut(plan)}
                className="flex-1 bg-brass-dark text-white text-center min-h-10 py-2 rounded-lg text-[12.5px] font-semibold disabled:opacity-50 cursor-pointer"
              >
                {busyId === plan.id ? "Working…" : "Cash out"}
              </button>
              <button
                type="button"
                disabled={busyId === plan.id}
                onClick={() => onReopen(plan)}
                className="flex-1 border border-brass-dark text-brass-dark text-center min-h-10 py-2 rounded-lg text-[12.5px] font-semibold disabled:opacity-50 cursor-pointer"
              >
                Switch back on
              </button>
            </div>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={onClose}
        className="text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold bg-emerald text-white cursor-pointer"
      >
        Done
      </button>
    </BottomSheet>
  );
}
