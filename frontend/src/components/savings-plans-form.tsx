"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { api, ApiError } from "@/lib/api";
import { annualFromMonthly } from "@/lib/format";
import type { SavingsPlanOut } from "@/lib/types";

const DEFAULT_RATE = 1.0;
const DEFAULT_LOCK_MONTHS = 6;

function clampRate(v: number): number {
  return Math.min(100, Math.max(0.1, Math.round(v * 10) / 10));
}

function planTypeLabel(lockMonths: number): string {
  if (lockMonths <= 0) return "Flexible — withdraw any time";
  return `Locked for ${lockMonths} ${lockMonths === 1 ? "month" : "months"}`;
}

export function SavingsPlansForm({ initialPlans }: { initialPlans: SavingsPlanOut[] }) {
  const { data: session } = useSession();
  const router = useRouter();

  const [kind, setKind] = useState<"flexible" | "locked">("flexible");
  const [name, setName] = useState("");
  const [rate, setRate] = useState(DEFAULT_RATE);
  const [lockMonths, setLockMonths] = useState(DEFAULT_LOCK_MONTHS);
  const [creating, setCreating] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const annual = annualFromMonthly(rate);

  async function handleCreate() {
    if (!session?.backendToken || !name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await api.post("/family/savings-plans", session.backendToken, {
        name: name.trim(),
        monthly_rate: rate,
        lock_months: kind === "locked" ? lockMonths : 0,
      });
      setName("");
      setRate(DEFAULT_RATE);
      setLockMonths(DEFAULT_LOCK_MONTHS);
      setKind("flexible");
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setCreating(false);
    }
  }

  async function handleToggleActive(plan: SavingsPlanOut) {
    if (!session?.backendToken) return;
    setBusyId(plan.id);
    setError(null);
    try {
      await api.patch(`/family/savings-plans/${plan.id}`, session.backendToken, {
        is_active: !plan.is_active,
      });
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(plan: SavingsPlanOut) {
    if (!session?.backendToken) return;
    const warning =
      plan.open_deposit_count > 0
        ? `${plan.open_deposit_count} deposit${plan.open_deposit_count === 1 ? "" : "s"} ${
            plan.open_deposit_count === 1 ? "is" : "are"
          } in this plan. Deleting it won't touch those savings — they keep growing at the same rate — you just can't add new money to it. Delete anyway?`
        : `Delete "${plan.name}"?`;
    if (!confirm(warning)) return;
    setBusyId(plan.id);
    setError(null);
    try {
      await api.delete(`/family/savings-plans/${plan.id}`, session.backendToken);
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex flex-col gap-6 px-5 pt-4 pb-10">
      <div className="flex flex-col gap-3 text-[13.5px] text-muted leading-relaxed">
        <p>
          A savings plan is a place for your kid to park cash and earn interest on it. You set the
          rate; they see it grow a little every day.
        </p>
        <p>
          The rate is <strong>monthly</strong>. It compounds, so a monthly rate works out to a lot
          more over a year — the yearly figure is shown next to each plan.
        </p>
        <p>
          A <strong>flexible</strong> plan can be cashed out any time. A <strong>locked</strong>{" "}
          plan can&apos;t be touched until its term is up — then it keeps earning the same rate
          until your kid withdraws it.
        </p>
      </div>

      {initialPlans.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <span className="text-[12px] font-semibold text-muted">Your plans</span>
          {initialPlans.map((plan) => (
            <div
              key={plan.id}
              className={`bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex flex-col gap-1.5 ${
                plan.is_active ? "" : "opacity-60"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-[14.5px] text-emerald-dark">{plan.name}</span>
                <span className="text-[13px] font-semibold text-emerald">
                  {Number(plan.monthly_rate).toFixed(1)}%/mo
                </span>
              </div>
              <div className="flex items-center justify-between gap-2 text-[12px] text-muted">
                <span>{planTypeLabel(plan.lock_months)}</span>
                <span>≈ {Number(plan.annual_rate).toFixed(1)}%/year</span>
              </div>
              {plan.open_deposit_count > 0 && (
                <span className="text-[11.5px] text-muted">
                  {plan.open_deposit_count} open deposit{plan.open_deposit_count === 1 ? "" : "s"}
                </span>
              )}
              <div className="flex gap-4 pt-1">
                <button
                  type="button"
                  disabled={busyId === plan.id}
                  onClick={() => handleToggleActive(plan)}
                  className="text-[12.5px] font-semibold text-emerald cursor-pointer disabled:opacity-50"
                >
                  {plan.is_active ? "Hide from kids" : "Make available"}
                </button>
                <button
                  type="button"
                  disabled={busyId === plan.id}
                  onClick={() => handleDelete(plan)}
                  className="text-[12.5px] font-semibold text-negative cursor-pointer disabled:opacity-50"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-3">
        <span className="text-[12px] font-semibold text-muted">Add a plan</span>

        <label className="flex flex-col gap-1.5">
          <span className="text-[12px] font-semibold text-muted">Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Rainy day fund"
            maxLength={60}
            className="border border-border-hairline-strong rounded-[10px] px-3.5 py-3 text-[14.5px] text-emerald-dark outline-none focus:border-emerald bg-card"
          />
        </label>

        <SegmentedControl
          value={kind}
          onChange={setKind}
          options={[
            { value: "flexible", label: "Flexible" },
            { value: "locked", label: "Locked" },
          ]}
        />

        {kind === "locked" && (
          <div className="flex flex-col gap-1.5">
            <span className="text-[12px] font-semibold text-muted">Locked for</span>
            <div className="flex items-center gap-3 bg-card rounded-2xl px-4 py-3 border border-border-hairline">
              <button
                type="button"
                onClick={() => setLockMonths((m) => Math.max(1, m - 1))}
                className="w-9 h-9 shrink-0 rounded-full bg-tint-neutral text-emerald-dark font-semibold text-[18px] cursor-pointer"
                aria-label="Fewer months"
              >
                −
              </button>
              <span className="flex-1 text-center font-serif font-semibold text-[18px] text-emerald-dark">
                {lockMonths} {lockMonths === 1 ? "month" : "months"}
              </span>
              <button
                type="button"
                onClick={() => setLockMonths((m) => Math.min(120, m + 1))}
                className="w-9 h-9 shrink-0 rounded-full bg-tint-neutral text-emerald-dark font-semibold text-[18px] cursor-pointer"
                aria-label="More months"
              >
                +
              </button>
            </div>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <span className="text-[12px] font-semibold text-muted">Monthly interest rate</span>
          <div className="flex items-center gap-3 bg-card rounded-2xl px-4 py-3 border border-border-hairline">
            <button
              type="button"
              onClick={() => setRate((r) => clampRate(r - 0.1))}
              className="w-9 h-9 shrink-0 rounded-full bg-tint-neutral text-emerald-dark font-semibold text-[18px] cursor-pointer"
              aria-label="Decrease"
            >
              −
            </button>
            <span className="flex-1 text-center font-serif font-semibold text-[22px] text-emerald-dark">
              {rate.toFixed(1)}%<span className="text-[13px] font-sans font-normal text-muted"> / month</span>
            </span>
            <button
              type="button"
              onClick={() => setRate((r) => clampRate(r + 0.1))}
              className="w-9 h-9 shrink-0 rounded-full bg-tint-neutral text-emerald-dark font-semibold text-[18px] cursor-pointer"
              aria-label="Increase"
            >
              +
            </button>
          </div>
          <p className="text-[11.5px] text-muted/80">
            ≈ {annual.toFixed(1)}%/year once it compounds.
          </p>
        </div>

        {error && <p className="text-[13px] text-negative">{error}</p>}

        <button
          type="button"
          disabled={creating || !name.trim()}
          onClick={handleCreate}
          className="bg-emerald text-white text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold disabled:opacity-50 cursor-pointer"
        >
          {creating ? "Creating…" : "Create plan"}
        </button>
      </div>
    </div>
  );
}
