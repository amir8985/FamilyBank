"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { annualFromMonthly } from "@/lib/format";
import type { SavingsPlanOut, SavingsPresetOut } from "@/lib/types";

type Kind = "flexible" | "locked";

function clampRate(v: number): number {
  return Math.min(100, Math.max(0.1, Math.round(v * 10) / 10));
}

function termLabel(lockMonths: number): string {
  if (lockMonths <= 0) return "Flexible — withdraw any time";
  if (lockMonths === 12) return "Locked for 1 year";
  return `Locked for ${lockMonths} ${lockMonths === 1 ? "month" : "months"}`;
}

export function SavingsKindForm({
  kind,
  plans,
  presets,
}: {
  kind: Kind;
  plans: SavingsPlanOut[];
  presets: SavingsPresetOut[];
}) {
  const { data: session } = useSession();
  const router = useRouter();

  const kindPresets = presets.filter((p) => p.kind === kind);
  const inKind = (p: SavingsPlanOut) => (kind === "flexible" ? p.lock_months === 0 : p.lock_months > 0);
  const customPlans = plans.filter((p) => p.preset_key === null && inKind(p));

  const [name, setName] = useState("");
  const [rate, setRate] = useState(kind === "locked" ? 3.0 : 1.0);
  const [lockMonths, setLockMonths] = useState(6);
  const [creating, setCreating] = useState(false);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function togglePreset(preset: SavingsPresetOut, on: boolean) {
    if (!session?.backendToken) return;
    setBusyKey(preset.key);
    setError(null);
    try {
      await api.post("/family/savings-presets", session.backendToken, { key: preset.key, active: on });
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setBusyKey(null);
    }
  }

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
      setRate(kind === "locked" ? 3.0 : 1.0);
      setLockMonths(6);
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setCreating(false);
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
    setBusyKey(plan.id);
    setError(null);
    try {
      await api.delete(`/family/savings-plans/${plan.id}`, session.backendToken);
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <div className="flex flex-col gap-6 px-5 pt-4 pb-10">
      <div className="flex flex-col gap-3 text-[13.5px] text-muted leading-relaxed">
        {kind === "flexible" ? (
          <p>
            Your kid can move cash into a flexible plan and pull it back out any time. It earns
            interest every day it&apos;s in there.
          </p>
        ) : (
          <p>
            A locked plan can&apos;t be touched until its term is up — in exchange for a higher
            rate. When the term ends it keeps earning the same rate until your kid withdraws.
          </p>
        )}
        <p>
          Rates are <strong>monthly</strong> and compound, so the yearly figure (shown on each
          plan) works out higher than twelve times the monthly one.
        </p>
      </div>

      <div className="flex flex-col gap-2.5">
        <span className="text-[12px] font-semibold text-muted">Ready-made plans</span>
        {kindPresets.map((preset) => {
          const existing = plans.find((p) => p.preset_key === preset.key);
          const on = Boolean(existing?.is_active);
          return (
            <label
              key={preset.key}
              className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex items-center justify-between gap-3 cursor-pointer"
            >
              <div>
                <div className="font-semibold text-[14.5px] text-emerald-dark">{preset.name}</div>
                <div className="text-[12px] text-muted">
                  {Number(preset.monthly_rate).toFixed(1)}%/mo · ≈ {Number(preset.annual_rate).toFixed(1)}%/year
                  {kind === "locked" ? ` · ${termLabel(preset.lock_months).replace("Locked for ", "")}` : ""}
                </div>
                {existing && !existing.is_active && existing.open_deposit_count > 0 && (
                  <div className="text-[11px] text-muted mt-0.5">
                    Off, but {existing.open_deposit_count} deposit
                    {existing.open_deposit_count === 1 ? "" : "s"} still growing in it
                  </div>
                )}
              </div>
              <input
                type="checkbox"
                checked={on}
                disabled={busyKey === preset.key}
                onChange={(e) => togglePreset(preset, e.target.checked)}
                className="w-5 h-5 accent-emerald cursor-pointer shrink-0"
              />
            </label>
          );
        })}
      </div>

      {customPlans.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <span className="text-[12px] font-semibold text-muted">Your own plans</span>
          {customPlans.map((plan) => (
            <div
              key={plan.id}
              className={`bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex flex-col gap-1 ${
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
                <span>{termLabel(plan.lock_months)}</span>
                <span>≈ {Number(plan.annual_rate).toFixed(1)}%/year</span>
              </div>
              {plan.open_deposit_count > 0 && (
                <span className="text-[11.5px] text-muted">
                  {plan.open_deposit_count} open deposit{plan.open_deposit_count === 1 ? "" : "s"}
                </span>
              )}
              <button
                type="button"
                disabled={busyKey === plan.id}
                onClick={() => handleDelete(plan)}
                className="self-start text-[12.5px] font-semibold text-negative cursor-pointer disabled:opacity-50 pt-1"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-3">
        <span className="text-[12px] font-semibold text-muted">Add your own</span>

        <label className="flex flex-col gap-1.5">
          <span className="text-[12px] font-semibold text-muted">Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={kind === "locked" ? "e.g. Summer camp fund" : "e.g. Rainy day fund"}
            maxLength={60}
            className="border border-border-hairline-strong rounded-[10px] px-3.5 py-3 text-[14.5px] text-emerald-dark outline-none focus:border-emerald bg-card"
          />
        </label>

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
            ≈ {annualFromMonthly(rate).toFixed(1)}%/year once it compounds.
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
