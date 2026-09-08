"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { ConfirmSheet } from "@/components/ui/confirm-sheet";
import { StillGrowingBadge } from "@/components/ui/still-growing-badge";
import { SavingsChangesSheet, type AffectedPlan } from "@/components/savings-changes-sheet";
import { annualFromMonthly } from "@/lib/format";
import type { PlanDepositOut, SavingsPlanOut, SavingsPresetOut } from "@/lib/types";

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
  const token = session?.backendToken;
  const router = useRouter();

  const kindPresets = presets.filter((p) => p.kind === kind);
  const inKind = (p: SavingsPlanOut) => (kind === "flexible" ? p.lock_months === 0 : p.lock_months > 0);
  const customPlans = plans.filter((p) => p.preset_key === null && inKind(p));

  const serverPresetOn = (key: string) => plans.some((p) => p.preset_key === key && p.is_active);
  const serverCustomOn = (id: string) => plans.find((p) => p.id === id)?.is_active ?? false;

  // Staged toggle changes — nothing is written until "Save changes".
  const [override, setOverride] = useState<Record<string, boolean>>({});
  // Reset staged state whenever the server data changes under us (after a
  // save + refresh). React's documented "adjust state during render".
  const sig = plans.map((p) => `${p.id}:${p.is_active}`).join("|");
  const [lastSig, setLastSig] = useState(sig);
  if (sig !== lastSig) {
    setLastSig(sig);
    setOverride({});
  }

  const presetOn = (key: string) => override[`preset:${key}`] ?? serverPresetOn(key);
  const customOn = (id: string) => override[`custom:${id}`] ?? serverCustomOn(id);
  const dirty = Object.entries(override).some(([k, v]) => {
    const id = k.slice(k.indexOf(":") + 1);
    return k.startsWith("preset:") ? serverPresetOn(id) !== v : serverCustomOn(id) !== v;
  });

  const [name, setName] = useState("");
  const [rate, setRate] = useState(kind === "locked" ? 3.0 : 1.0);
  const [lockMonths, setLockMonths] = useState(6);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SavingsPlanOut | null>(null);
  const [changeSheet, setChangeSheet] = useState<AffectedPlan[] | null>(null);

  function stagePreset(key: string, on: boolean) {
    setOverride((o) => ({ ...o, [`preset:${key}`]: on }));
  }
  function stageCustom(id: string, on: boolean) {
    setOverride((o) => ({ ...o, [`custom:${id}`]: on }));
  }

  // Plans being switched off (vs. server) that still hold a kid's money.
  function turningOffWithDeposits(): SavingsPlanOut[] {
    const out: SavingsPlanOut[] = [];
    for (const preset of kindPresets) {
      const existing = plans.find((p) => p.preset_key === preset.key);
      if (existing?.is_active && !presetOn(preset.key) && existing.open_deposit_count > 0) out.push(existing);
    }
    for (const plan of customPlans) {
      if (plan.is_active && !customOn(plan.id) && plan.open_deposit_count > 0) out.push(plan);
    }
    return out;
  }

  async function applyToggles() {
    if (!token) return;
    for (const preset of kindPresets) {
      const want = presetOn(preset.key);
      if (want !== serverPresetOn(preset.key)) {
        await api.post("/family/savings-presets", token, { key: preset.key, active: want });
      }
    }
    for (const plan of customPlans) {
      const want = customOn(plan.id);
      if (want !== serverCustomOn(plan.id)) {
        await api.patch(`/family/savings-plans/${plan.id}`, token, { is_active: want });
      }
    }
  }

  async function runSave(work: () => Promise<void>) {
    setSaving(true);
    setError(null);
    try {
      await work();
      setOverride({});
      setChangeSheet(null);
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setSaving(false);
    }
  }

  async function handleSave() {
    if (!token) return;
    const affected = turningOffWithDeposits();
    if (affected.length === 0) {
      await runSave(applyToggles);
      return;
    }
    try {
      const withDeposits: AffectedPlan[] = await Promise.all(
        affected.map(async (plan) => ({
          plan,
          deposits: await api.get<PlanDepositOut[]>(`/family/savings-plans/${plan.id}/deposits`, token),
        })),
      );
      setChangeSheet(withDeposits);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    }
  }

  async function handleCreate() {
    if (!token || !name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await api.post("/family/savings-plans", token, {
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

  async function confirmDelete() {
    if (!token || !deleteTarget) return;
    await runSave(async () => {
      await api.delete(`/family/savings-plans/${deleteTarget.id}`, token);
      setDeleteTarget(null);
    });
  }

  const badgeFor = (plan: SavingsPlanOut | undefined, on: boolean) =>
    plan && !on && plan.open_deposit_count > 0 ? (
      <StillGrowingBadge count={plan.open_deposit_count} rate={String(plan.monthly_rate)} />
    ) : null;

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
        <span className="text-[12px] font-semibold text-muted">Recommended plans</span>
        {kindPresets.map((preset) => {
          const existing = plans.find((p) => p.preset_key === preset.key);
          const on = presetOn(preset.key);
          return (
            <div key={preset.key} className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex flex-col gap-1.5">
              <label className="flex items-center justify-between gap-3 cursor-pointer">
                <div>
                  <div className="font-semibold text-[14.5px] text-emerald-dark">{preset.name}</div>
                  <div className="text-[12px] text-muted">
                    {Number(preset.monthly_rate).toFixed(1)}%/mo · ≈ {Number(preset.annual_rate).toFixed(1)}%/year
                    {kind === "locked" ? ` · ${termLabel(preset.lock_months).replace("Locked for ", "")}` : ""}
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={on}
                  onChange={(e) => stagePreset(preset.key, e.target.checked)}
                  className="w-5 h-5 accent-emerald cursor-pointer shrink-0"
                />
              </label>
              {badgeFor(existing, on)}
            </div>
          );
        })}
      </div>

      {customPlans.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <span className="text-[12px] font-semibold text-muted">Your own plans</span>
          {customPlans.map((plan) => {
            const on = customOn(plan.id);
            return (
              <div
                key={plan.id}
                className={`bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex flex-col gap-1 ${
                  on ? "" : "opacity-70"
                }`}
              >
                <label className="flex items-center justify-between gap-3 cursor-pointer">
                  <div>
                    <div className="font-semibold text-[14.5px] text-emerald-dark">{plan.name}</div>
                    <div className="text-[12px] text-muted">
                      {termLabel(plan.lock_months)} · {Number(plan.monthly_rate).toFixed(1)}%/mo · ≈{" "}
                      {Number(plan.annual_rate).toFixed(1)}%/year
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={(e) => stageCustom(plan.id, e.target.checked)}
                    className="w-5 h-5 accent-emerald cursor-pointer shrink-0"
                  />
                </label>
                {badgeFor(plan, on)}
                <button
                  type="button"
                  onClick={() => setDeleteTarget(plan)}
                  className="self-start text-[12.5px] font-semibold text-negative cursor-pointer pt-1"
                >
                  Delete
                </button>
              </div>
            );
          })}
        </div>
      )}

      {error && <p className="text-[13px] text-negative">{error}</p>}

      {dirty && (
        <button
          type="button"
          disabled={saving}
          onClick={handleSave}
          className="bg-emerald text-white text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold disabled:opacity-50 cursor-pointer"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
      )}

      <div className="flex flex-col gap-3 border-t border-border-hairline-strong pt-6">
        <span className="text-[12px] font-semibold text-muted">Add your own plan</span>

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

        <button
          type="button"
          disabled={creating || !name.trim()}
          onClick={handleCreate}
          className="bg-emerald text-white text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold disabled:opacity-50 cursor-pointer"
        >
          {creating ? "Creating…" : "Create plan"}
        </button>
      </div>

      {deleteTarget && (
        <ConfirmSheet
          title={`Delete "${deleteTarget.name}"?`}
          confirmLabel="Delete plan"
          confirming={saving}
          onConfirm={confirmDelete}
          onClose={() => setDeleteTarget(null)}
          body={
            deleteTarget.open_deposit_count > 0
              ? `${deleteTarget.open_deposit_count} deposit${
                  deleteTarget.open_deposit_count === 1 ? " is" : "s are"
                } in this plan. Deleting it won't touch those savings — they keep growing at the same rate — your kid just can't add new money to it.`
              : "This plan will be removed. You can always add it back later."
          }
        />
      )}

      {changeSheet && (
        <SavingsChangesSheet
          affected={changeSheet}
          working={saving}
          onClose={() => setChangeSheet(null)}
          onJustSave={() => runSave(applyToggles)}
          onCashOutAndSave={() =>
            runSave(async () => {
              for (const { plan } of changeSheet) {
                await api.post(`/family/savings-plans/${plan.id}/cash-out`, token!);
              }
              await applyToggles();
            })
          }
        />
      )}
    </div>
  );
}
