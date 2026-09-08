"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { api, ApiError } from "@/lib/api";
import { ConfirmSheet } from "@/components/ui/confirm-sheet";
import { PlanDepositMarker } from "@/components/ui/plan-deposit-marker";
import { SavingsLeftoversSheet, type LeftoverPlan } from "@/components/savings-leftovers-sheet";
import { useFamily } from "@/lib/family-store";
import { invalidateKid } from "@/lib/use-cached-resource";
import { useToast } from "@/components/ui/toast";
import { annualFromMonthly, formatMoney } from "@/lib/format";
import type { PlanDepositOut, SavingsPlanOut, SavingsPresetOut } from "@/lib/types";

type Kind = "flexible" | "locked";

type MutatePlans = (updater: (prev: SavingsPlanOut[] | undefined) => SavingsPlanOut[]) => () => void;

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
  mutatePlans,
  revalidatePlans,
}: {
  kind: Kind;
  plans: SavingsPlanOut[];
  presets: SavingsPresetOut[];
  mutatePlans: MutatePlans;
  revalidatePlans: () => Promise<void>;
}) {
  const { data: session } = useSession();
  const token = session?.backendToken;
  const { refreshHome } = useFamily();
  const toast = useToast();

  const kindPresets = presets.filter((p) => p.kind === kind);
  const inKind = (p: SavingsPlanOut) => (kind === "flexible" ? p.lock_months === 0 : p.lock_months > 0);
  const customPlans = plans.filter((p) => p.preset_key === null && inKind(p));

  const serverPresetOn = (key: string) => plans.some((p) => p.preset_key === key && p.is_active);
  const serverCustomOn = (id: string) => plans.find((p) => p.id === id)?.is_active ?? false;

  // Nothing is written until "Save changes" — a checkbox only stages.
  const [override, setOverride] = useState<Record<string, boolean>>({});

  const serverStateOf = (k: string) =>
    k.startsWith("preset:")
      ? serverPresetOn(k.slice("preset:".length))
      : serverCustomOn(k.slice("custom:".length));

  // When the cached plan list changes under us (optimistic mutate,
  // background revalidate, another tab), prune any staged entry that the
  // server now agrees with — keeps a still-pending selection intact if a
  // failed save rolls the cache back. React's "adjust state during render".
  const sig = plans.map((p) => `${p.id}:${p.is_active}`).join("|");
  const [lastSig, setLastSig] = useState(sig);
  if (sig !== lastSig) {
    setLastSig(sig);
    setOverride((o) => {
      const pruned = Object.fromEntries(
        Object.entries(o).filter(([k, v]) => serverStateOf(k) !== v),
      );
      return Object.keys(pruned).length === Object.keys(o).length ? o : pruned;
    });
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
  // Separate from `saving` (the sticky toggle-Save bar) so a delete /
  // cash-out running in a modal doesn't make the Save bar say "Saving…".
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SavingsPlanOut | null>(null);
  const [leftovers, setLeftovers] = useState<LeftoverPlan[] | null>(null);
  const [leftoverBusy, setLeftoverBusy] = useState<string | null>(null);
  const [cashOutTarget, setCashOutTarget] = useState<LeftoverPlan | null>(null);
  const [openingCashOut, setOpeningCashOut] = useState<string | null>(null);

  function stagePreset(key: string, on: boolean) {
    setOverride((o) => ({ ...o, [`preset:${key}`]: on }));
  }
  function stageCustom(id: string, on: boolean) {
    setOverride((o) => ({ ...o, [`custom:${id}`]: on }));
  }

  type ToggleChange =
    | { kind: "preset"; key: string; want: boolean }
    | { kind: "custom"; id: string; want: boolean };

  // Snapshot the pending changes from `override` vs. the server. Must be
  // read *before* any optimistic cache mutate, which would otherwise make
  // these look already-applied.
  function pendingChanges(): ToggleChange[] {
    const out: ToggleChange[] = [];
    for (const preset of kindPresets) {
      const want = presetOn(preset.key);
      if (want !== serverPresetOn(preset.key)) out.push({ kind: "preset", key: preset.key, want });
    }
    for (const plan of customPlans) {
      const want = customOn(plan.id);
      if (want !== serverCustomOn(plan.id)) out.push({ kind: "custom", id: plan.id, want });
    }
    return out;
  }

  async function applyChanges(changes: ToggleChange[]) {
    if (!token) return;
    for (const c of changes) {
      if (c.kind === "preset") {
        await api.post("/family/savings-presets", token, { key: c.key, active: c.want });
      } else {
        await api.patch(`/family/savings-plans/${c.id}`, token, { is_active: c.want });
      }
    }
  }

  // Plans this pending save switches OFF (vs. the server) that still
  // hold a deposit — the only thing worth prompting about after a save.
  // A plan that was already off before this save is *not* included, so
  // saving an unrelated change (e.g. turning a different plan on) never
  // pops the leftovers sheet.
  function turnedOffWithDeposits(): SavingsPlanOut[] {
    const out: SavingsPlanOut[] = [];
    for (const preset of kindPresets) {
      const existing = plans.find((p) => p.preset_key === preset.key);
      if (existing?.is_active && !presetOn(preset.key) && existing.open_deposit_count > 0) {
        out.push(existing);
      }
    }
    for (const plan of customPlans) {
      if (plan.is_active && !customOn(plan.id) && plan.open_deposit_count > 0) out.push(plan);
    }
    return out;
  }

  // Optimistically flip the cached plan rows to the just-staged state so
  // the checkboxes stay put the instant Save is pressed; reconciled by
  // revalidatePlans() once the writes land.
  function optimisticApply(changes: ToggleChange[]): () => void {
    return mutatePlans((prev) =>
      (prev ?? []).map((p) => {
        const hit = changes.find((c) =>
          c.kind === "preset" ? p.preset_key === c.key : p.id === c.id,
        );
        return hit ? { ...p, is_active: hit.want } : p;
      }),
    );
  }

  async function cashOutOne(plan: SavingsPlanOut, deposits: PlanDepositOut[]) {
    if (!token) return;
    await api.post(`/family/savings-plans/${plan.id}/cash-out`, token);
    // Each kid's money is back in their cash — refresh the home store and
    // drop their cached portfolio/savings so those screens are correct
    // next time they're opened.
    for (const d of deposits) invalidateKid(d.kid_id);
    refreshHome();
  }

  async function handleSave() {
    if (!token) return;
    const affected = turnedOffWithDeposits();
    const changes = pendingChanges();
    setSaving(true);
    setError(null);
    const rollback = optimisticApply(changes);
    try {
      await applyChanges(changes);
      const left: LeftoverPlan[] =
        affected.length === 0
          ? []
          : await Promise.all(
              affected.map(async (plan) => ({
                plan,
                deposits: await api.get<PlanDepositOut[]>(
                  `/family/savings-plans/${plan.id}/deposits`,
                  token,
                ),
              })),
            );
      setOverride({});
      revalidatePlans();
      if (left.length > 0) setLeftovers(left);
    } catch (e) {
      rollback();
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setSaving(false);
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
      revalidatePlans();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setCreating(false);
    }
  }

  async function confirmDelete() {
    if (!token || !deleteTarget) return;
    const id = deleteTarget.id;
    setBusy(true);
    setError(null);
    const rollback = mutatePlans((prev) => (prev ?? []).filter((p) => p.id !== id));
    setDeleteTarget(null);
    try {
      await api.delete(`/family/savings-plans/${id}`, token);
      revalidatePlans();
    } catch (e) {
      rollback();
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function resolveLeftover(plan: SavingsPlanOut, action: "cash-out" | "reopen") {
    if (!token) return;
    const entry = (leftovers ?? []).find((l) => l.plan.id === plan.id);
    setLeftoverBusy(plan.id);
    setError(null);
    try {
      if (action === "cash-out") {
        await cashOutOne(plan, entry?.deposits ?? []);
      } else if (plan.preset_key) {
        await api.post("/family/savings-presets", token, { key: plan.preset_key, active: true });
      } else {
        await api.patch(`/family/savings-plans/${plan.id}`, token, { is_active: true });
      }
      setLeftovers((cur) => {
        const next = (cur ?? []).filter((l) => l.plan.id !== plan.id);
        return next.length ? next : null;
      });
      revalidatePlans();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setLeftoverBusy(null);
    }
  }

  async function openCashOut(plan: SavingsPlanOut) {
    if (!token || openingCashOut) return;
    setOpeningCashOut(plan.id);
    setError(null);
    try {
      const deposits = await api.get<PlanDepositOut[]>(
        `/family/savings-plans/${plan.id}/deposits`,
        token,
      );
      setCashOutTarget({ plan, deposits });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setOpeningCashOut(null);
    }
  }

  async function confirmCashOut() {
    if (!token || !cashOutTarget) return;
    const target = cashOutTarget;
    setBusy(true);
    setError(null);
    setCashOutTarget(null);
    try {
      await cashOutOne(target.plan, target.deposits);
      revalidatePlans();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
      toast(e instanceof ApiError ? e.message : "Cash-out failed", "error");
    } finally {
      setBusy(false);
    }
  }

  const planExtras = (plan: SavingsPlanOut | undefined) => {
    if (!plan || plan.open_deposit_count === 0) return null;
    return (
      <>
        <PlanDepositMarker
          count={plan.open_deposit_count}
          active={plan.is_active}
          locked={plan.lock_months > 0}
          rate={String(plan.monthly_rate)}
        />
        {!plan.is_active && (
          <button
            type="button"
            disabled={openingCashOut === plan.id}
            onClick={() => openCashOut(plan)}
            className="self-start text-[12.5px] font-semibold text-brass-dark cursor-pointer disabled:opacity-50 pt-1"
          >
            {openingCashOut === plan.id ? "Loading…" : "Cash out these savings"}
          </button>
        )}
      </>
    );
  };

  return (
    <div className="flex flex-col">
      {dirty && (
        <div className="sticky top-0 z-20 bg-cream/95 backdrop-blur border-b border-border-hairline-strong px-5 py-2.5">
          <button
            type="button"
            disabled={saving}
            onClick={handleSave}
            className="w-full bg-emerald text-white text-center min-h-11 py-[12px] rounded-xl text-[14px] font-semibold disabled:opacity-50 cursor-pointer"
          >
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      )}

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
          <p className="text-[12.5px]">
            Turn plans on or off with the checkboxes, then <strong>Save changes</strong>.
          </p>
        </div>

        <div className="flex flex-col gap-2.5">
          <span className="text-[12px] font-semibold text-muted">Recommended plans</span>
          {kindPresets.map((preset) => {
            const existing = plans.find((p) => p.preset_key === preset.key);
            const on = presetOn(preset.key);
            return (
              <div
                key={preset.key}
                className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex flex-col gap-1.5"
              >
                <label className="flex items-center justify-between gap-3 cursor-pointer">
                  <div>
                    <div className="font-semibold text-[14.5px] text-emerald-dark">{preset.name}</div>
                    <div className="text-[12px] text-muted">
                      {Number(preset.monthly_rate).toFixed(1)}%/mo · ≈{" "}
                      {Number(preset.annual_rate).toFixed(1)}%/year
                      {kind === "locked"
                        ? ` · ${termLabel(preset.lock_months).replace("Locked for ", "")}`
                        : ""}
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={(e) => stagePreset(preset.key, e.target.checked)}
                    className="w-5 h-5 accent-emerald cursor-pointer shrink-0"
                  />
                </label>
                {planExtras(existing)}
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
                  {planExtras(plan)}
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
                {rate.toFixed(1)}%
                <span className="text-[13px] font-sans font-normal text-muted"> / month</span>
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
      </div>

      {deleteTarget && (
        <ConfirmSheet
          title={`Delete "${deleteTarget.name}"?`}
          confirmLabel="Delete plan"
          confirming={busy}
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

      {leftovers && (
        <SavingsLeftoversSheet
          leftovers={leftovers}
          busyId={leftoverBusy}
          onClose={() => setLeftovers(null)}
          onCashOut={(plan) => resolveLeftover(plan, "cash-out")}
          onReopen={(plan) => resolveLeftover(plan, "reopen")}
        />
      )}

      {cashOutTarget && (
        <ConfirmSheet
          title={`Cash out "${cashOutTarget.plan.name}"?`}
          confirmLabel="Cash out now"
          confirming={busy}
          onConfirm={confirmCashOut}
          onClose={() => setCashOutTarget(null)}
          body={
            <span className="flex flex-col gap-2">
              <span>
                {cashOutTarget.plan.lock_months > 0
                  ? "Closes every deposit in this plan now — even ones whose lock term isn't up — and pays each back to your kid's cash, interest included."
                  : "Closes every deposit in this plan now and pays each back to your kid's cash, interest included."}
              </span>
              <span className="flex flex-col gap-0.5">
                {cashOutTarget.deposits.map((d) => (
                  <span key={d.kid_id} className="flex justify-between text-[12.5px]">
                    <span>{d.kid_name}</span>
                    <span className="font-semibold">{formatMoney(d.current_value, d.currency)}</span>
                  </span>
                ))}
              </span>
            </span>
          }
        />
      )}
    </div>
  );
}
