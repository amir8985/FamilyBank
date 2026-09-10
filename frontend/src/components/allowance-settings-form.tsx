"use client";

import { useMemo, useState } from "react";
import { Avatar } from "@/components/ui/avatar";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { ConfirmSheet } from "@/components/ui/confirm-sheet";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { useCachedResource, invalidateKid } from "@/lib/use-cached-resource";
import { useFamily } from "@/lib/family-store";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import {
  allowanceScheduleLabel,
  currencySymbol,
  formatDate,
  formatMoney,
  ordinal,
  WEEKDAYS,
} from "@/lib/format";
import type { AllowanceCadence, AllowanceOut, FamilyAllowancesOut } from "@/lib/types";

type Draft = {
  amount: string;
  cadence: AllowanceCadence;
  payday: number;
};

function draftFor(a: AllowanceOut | null): Draft {
  if (!a || !a.configured) return { amount: "", cadence: "weekly", payday: 0 };
  return { amount: a.amount ?? "", cadence: a.cadence ?? "weekly", payday: a.payday ?? 0 };
}

function defaultPaydayFor(cadence: AllowanceCadence, current: number): number {
  if (cadence === "weekly") return current >= 0 && current <= 6 ? current : 0;
  return current >= 1 && current <= 28 ? current : 1;
}

function scheduleSummary(a: AllowanceOut, currency: string): string {
  if (!a.configured || !a.amount || a.cadence == null || a.payday == null) return "";
  return `${formatMoney(a.amount, a.currency ?? currency)} ${allowanceScheduleLabel(a.cadence, a.payday)}`;
}

// --- shared form fields ------------------------------------------------

function AmountField({
  currency,
  value,
  onChange,
}: {
  currency: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[12px] font-semibold text-muted">Amount</span>
      <div className="flex items-center gap-1.5 border border-border-hairline-strong rounded-[10px] px-3.5 py-3 bg-card focus-within:border-emerald">
        <span className="text-[14.5px] text-muted-strong">{currencySymbol(currency)}</span>
        <input
          autoFocus
          inputMode="decimal"
          value={value}
          onChange={(e) => onChange(e.target.value.replace(/[^0-9.]/g, ""))}
          placeholder="0.00"
          className="flex-1 bg-transparent outline-none text-[14.5px] text-emerald-dark placeholder:text-emerald/30"
        />
      </div>
    </label>
  );
}

function CadenceField({
  value,
  onChange,
}: {
  value: AllowanceCadence;
  onChange: (c: AllowanceCadence) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[12px] font-semibold text-muted">How often</span>
      <SegmentedControl
        value={value}
        onChange={onChange}
        options={[
          { value: "weekly" as const, label: "Weekly" },
          { value: "monthly" as const, label: "Monthly" },
        ]}
      />
    </div>
  );
}

function PaydayField({
  cadence,
  value,
  onChange,
}: {
  cadence: AllowanceCadence;
  value: number;
  onChange: (n: number) => void;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[12px] font-semibold text-muted">
        {cadence === "weekly" ? "Which day" : "Day of the month"}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="border border-border-hairline-strong rounded-[10px] px-3.5 py-3 text-[14.5px] text-emerald-dark outline-none focus:border-emerald bg-card"
      >
        {cadence === "weekly"
          ? WEEKDAYS.map((d, i) => (
              <option key={i} value={i}>
                {d}
              </option>
            ))
          : Array.from({ length: 28 }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
      </select>
    </label>
  );
}

// --- editor sheet (set up / change one kid's allowance) --------------

function AllowanceEditorSheet({
  kidName,
  existing,
  currency,
  onClose,
  onSave,
}: {
  kidName: string;
  existing: AllowanceOut | null;
  currency: string;
  onClose: () => void;
  onSave: (draft: Draft) => Promise<void>;
}) {
  const [draft, setDraft] = useState<Draft>(draftFor(existing));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = Number(draft.amount) > 0;

  async function save() {
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onSave(draft);
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
      setBusy(false);
    }
  }

  return (
    <BottomSheet onClose={onClose}>
      <h2 className="font-serif font-semibold text-[19px] text-emerald-dark">
        {existing?.configured ? `${kidName}'s allowance` : `Set up ${kidName}'s allowance`}
      </h2>
      <AmountField currency={currency} value={draft.amount} onChange={(amount) => setDraft((d) => ({ ...d, amount }))} />
      <CadenceField
        value={draft.cadence}
        onChange={(cadence) => setDraft((d) => ({ ...d, cadence, payday: defaultPaydayFor(cadence, d.payday) }))}
      />
      <PaydayField cadence={draft.cadence} value={draft.payday} onChange={(payday) => setDraft((d) => ({ ...d, payday }))} />
      <p className="text-[12px] text-muted -mt-1">
        First payment is on the next {draft.cadence === "weekly" ? WEEKDAYS[draft.payday] : `${draft.payday}${ordinal(draft.payday)}`} — not right now.
      </p>
      {error && <p className="text-[13px] text-negative">{error}</p>}
      <button
        type="button"
        disabled={!valid || busy}
        onClick={save}
        className="bg-emerald text-white text-center min-h-11 py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        {busy ? "Saving…" : existing?.configured ? "Save changes" : "Start allowance"}
      </button>
    </BottomSheet>
  );
}

// --- main screen -----------------------------------------------------

export function AllowanceSettingsForm() {
  const { home, token, refreshHome } = useFamily();
  const toast = useToast();

  const colorByKid = useMemo(
    () => Object.fromEntries(home.kids.map((k) => [k.id, k.avatar_color])),
    [home.kids]
  );

  const { data, revalidate } = useCachedResource<FamilyAllowancesOut>(
    token ? "family-allowances" : null,
    () => api.get<FamilyAllowancesOut>("/family/allowances", token as string),
    { ttlMs: 30_000 }
  );

  const currency = data?.base_currency ?? "USD";
  const kids = data?.kids ?? [];
  const active = kids.filter((k) => k.configured);
  const unset = kids.filter((k) => !k.configured);

  const [editing, setEditing] = useState<AllowanceOut | null>(null);
  const [turningOff, setTurningOff] = useState<AllowanceOut | null>(null);
  const [offBusy, setOffBusy] = useState(false);
  const [everyoneOpen, setEveryoneOpen] = useState(false);

  async function afterWrite(kidIds: string[]) {
    kidIds.forEach(invalidateKid);
    await Promise.all([revalidate(), refreshHome()]);
  }

  async function saveOne(kidId: string, draft: Draft) {
    await api.put(`/kids/${kidId}/allowance`, token as string, {
      amount: Number(draft.amount),
      cadence: draft.cadence,
      payday: draft.payday,
    });
    await afterWrite([kidId]);
  }

  async function confirmTurnOff() {
    if (!turningOff) return;
    setOffBusy(true);
    try {
      await api.delete(`/kids/${turningOff.kid_id}/allowance`, token as string);
      await afterWrite([turningOff.kid_id]);
      setTurningOff(null);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn't turn it off", "error");
    } finally {
      setOffBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-7 px-5 pt-4 pb-10">
      <p className="text-[13.5px] text-muted leading-relaxed">
        A weekly or monthly top-up that lands in your kid&apos;s balance automatically. Each payment
        shows up in their balance history. The first payment is on the next payday — not the moment
        you set it up.
      </p>

      {!data &&
        [0, 1].map((i) => (
          <div key={i} className="bg-card rounded-2xl border border-border-hairline h-24 animate-pulse" />
        ))}

      {active.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <span className="text-[12px] font-semibold text-muted">Active allowances</span>
          {active.map((a) => (
            <div
              key={a.kid_id}
              className="flex flex-col gap-3 bg-card rounded-2xl px-4 py-4 border border-border-hairline"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2.5 min-w-0">
                  <Avatar name={a.kid_name} color={colorByKid[a.kid_id] ?? "amber"} size={32} />
                  <span className="font-semibold text-[14.5px] text-emerald-dark truncate">{a.kid_name}</span>
                </div>
                <span className="text-[10px] font-semibold rounded-full px-1.5 py-0.5 shrink-0 text-tint-dark bg-tint-emerald">
                  On
                </span>
              </div>
              <div className="text-[13px] text-emerald-dark font-medium -mt-1">{scheduleSummary(a, currency)}</div>
              <div className="text-[12px] text-muted -mt-2">
                {a.next_payday ? `Next payment ${formatDate(a.next_payday)}` : ""}
                {a.last_paid_at ? ` · last paid ${formatDate(a.last_paid_at)}` : " · not paid yet"}
              </div>
              <div className="flex gap-2.5 border-t border-border-hairline pt-3">
                <button
                  type="button"
                  onClick={() => setEditing(a)}
                  className="flex-1 min-h-11 bg-tint-emerald text-emerald text-center py-[11px] rounded-lg text-[13px] font-semibold cursor-pointer"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => setTurningOff(a)}
                  className="flex-1 min-h-11 bg-tint-negative text-negative text-center py-[11px] rounded-lg text-[13px] font-semibold border border-negative/20 cursor-pointer"
                >
                  Turn off
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {unset.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <span className="text-[12px] font-semibold text-muted">
            {active.length > 0 ? "No allowance yet" : "Set up an allowance"}
          </span>
          {unset.map((a) => (
            <button
              key={a.kid_id}
              type="button"
              disabled={!token}
              onClick={() => setEditing(a)}
              className="flex items-center justify-between gap-2 bg-card rounded-2xl px-4 py-3.5 border border-border-hairline cursor-pointer disabled:opacity-50"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <Avatar name={a.kid_name} color={colorByKid[a.kid_id] ?? "amber"} size={32} />
                <span className="font-semibold text-[14.5px] text-emerald-dark truncate">{a.kid_name}</span>
              </div>
              <span className="text-emerald font-semibold text-[13px] shrink-0">Set up ›</span>
            </button>
          ))}
        </div>
      )}

      {kids.length > 1 && (
        <div className="flex flex-col gap-2.5">
          {!everyoneOpen ? (
            <button
              type="button"
              onClick={() => setEveryoneOpen(true)}
              className="text-center min-h-11 p-3 text-muted font-semibold text-[13px] border-[1.5px] border-dashed border-border-hairline-strong rounded-2xl cursor-pointer"
            >
              Set the same allowance for every kid
            </button>
          ) : (
            <EveryoneCard
              currency={currency}
              existingNames={active.map((a) => a.kid_name)}
              disabled={!token}
              onCancel={() => setEveryoneOpen(false)}
              onApply={async (draft) => {
                await api.post("/family/allowances", token as string, {
                  amount: Number(draft.amount),
                  cadence: draft.cadence,
                  payday: draft.payday,
                });
                await afterWrite(kids.map((k) => k.kid_id));
                setEveryoneOpen(false);
              }}
            />
          )}
        </div>
      )}

      {data && kids.length === 0 && (
        <p className="text-center text-[13px] text-muted pt-2">No kids yet — add one in Settings first.</p>
      )}

      {editing && (
        <AllowanceEditorSheet
          kidName={editing.kid_name}
          existing={editing.configured ? editing : null}
          currency={currency}
          onClose={() => setEditing(null)}
          onSave={(draft) => saveOne(editing.kid_id, draft)}
        />
      )}

      {turningOff && (
        <ConfirmSheet
          title={`Turn off ${turningOff.kid_name}'s allowance?`}
          confirmLabel="Turn it off"
          confirming={offBusy}
          onConfirm={confirmTurnOff}
          onClose={() => setTurningOff(null)}
          body={`No more automatic payments. Money already paid stays in ${turningOff.kid_name}'s balance and history. You can set a new one up any time.`}
        />
      )}
    </div>
  );
}

function EveryoneCard({
  currency,
  existingNames,
  disabled,
  onCancel,
  onApply,
}: {
  currency: string;
  existingNames: string[];
  disabled: boolean;
  onCancel: () => void;
  onApply: (draft: Draft) => Promise<void>;
}) {
  const [draft, setDraft] = useState<Draft>({ amount: "", cadence: "weekly", payday: 0 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmReplace, setConfirmReplace] = useState(false);
  const valid = Number(draft.amount) > 0;

  async function run() {
    setBusy(true);
    setError(null);
    try {
      await onApply(draft);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
      setBusy(false);
      setConfirmReplace(false);
    }
  }

  function apply() {
    if (!valid || busy) return;
    if (existingNames.length > 0) setConfirmReplace(true);
    else run();
  }

  return (
    <div className="flex flex-col gap-3 bg-card rounded-2xl px-4 py-4 border border-border-hairline">
      <div className="flex items-center justify-between">
        <h2 className="font-serif font-semibold text-[15px] text-emerald-dark">Same for every kid</h2>
        <button type="button" onClick={onCancel} className="text-[12px] font-semibold text-muted cursor-pointer">
          Cancel
        </button>
      </div>
      <AmountField currency={currency} value={draft.amount} onChange={(amount) => setDraft((d) => ({ ...d, amount }))} />
      <CadenceField
        value={draft.cadence}
        onChange={(cadence) => setDraft((d) => ({ ...d, cadence, payday: defaultPaydayFor(cadence, d.payday) }))}
      />
      <PaydayField cadence={draft.cadence} value={draft.payday} onChange={(payday) => setDraft((d) => ({ ...d, payday }))} />
      {error && <p className="text-[13px] text-negative">{error}</p>}
      <button
        type="button"
        disabled={disabled || !valid || busy}
        onClick={apply}
        className="bg-emerald text-white text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        {busy ? "Applying…" : "Apply to all kids"}
      </button>

      {confirmReplace && (
        <ConfirmSheet
          title="Replace existing allowances?"
          confirmLabel="Replace all"
          confirming={busy}
          onConfirm={run}
          onClose={() => setConfirmReplace(false)}
          body={
            <span>
              {existingNames.length === 1
                ? `${existingNames[0]} already has an allowance.`
                : `${existingNames.slice(0, -1).join(", ")} and ${existingNames.at(-1)} already have an allowance.`}{" "}
              Applying this replaces {existingNames.length === 1 ? "it" : "them"} with{" "}
              {formatMoney(draft.amount || "0", currency)}{" "}
              {allowanceScheduleLabel(draft.cadence, draft.payday)}.
            </span>
          }
        />
      )}
    </div>
  );
}
