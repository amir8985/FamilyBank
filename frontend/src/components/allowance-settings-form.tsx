"use client";

import { useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { Avatar } from "@/components/ui/avatar";
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
} from "@/lib/format";
import type { AllowanceCadence, AllowanceOut, FamilyAllowancesOut } from "@/lib/types";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

type Draft = {
  amount: string;
  cadence: AllowanceCadence;
  payday: number;
  is_active: boolean;
};

function draftFromServer(a: AllowanceOut | undefined): Draft {
  if (!a || !a.configured) {
    return { amount: "", cadence: "weekly", payday: 0, is_active: true };
  }
  return {
    amount: a.amount ?? "",
    cadence: a.cadence ?? "weekly",
    payday: a.payday ?? 0,
    is_active: a.is_active,
  };
}

function defaultPaydayFor(cadence: AllowanceCadence, current: number): number {
  if (cadence === "weekly") return current >= 0 && current <= 6 ? current : 0;
  return current >= 1 && current <= 28 ? current : 1;
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
        {cadence === "weekly" ? "Payday" : "Day of the month"}
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

export function AllowanceSettingsForm() {
  const { data: session } = useSession();
  const token = session?.backendToken ?? null;
  const { home, refreshHome } = useFamily();
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

  async function afterWrite(kidIds: string[]) {
    kidIds.forEach(invalidateKid);
    await Promise.all([revalidate(), refreshHome()]);
  }

  return (
    <div className="flex flex-col gap-7 px-5 pt-4 pb-10">
      <p className="text-[13.5px] text-muted leading-relaxed">
        A weekly or monthly top-up that lands in your kid&apos;s balance automatically. Each payment
        shows up in their balance history like any other. The first payment is on the next payday —
        it isn&apos;t paid the moment you set it up.
      </p>

      {kids.length > 1 && (
        <EveryoneCard
          currency={currency}
          disabled={!token}
          onApply={async (draft) => {
            await api.post("/family/allowances", token as string, {
              amount: Number(draft.amount),
              cadence: draft.cadence,
              payday: draft.payday,
              is_active: draft.is_active,
            });
            await afterWrite(kids.map((k) => k.kid_id));
          }}
        />
      )}

      <div className="flex flex-col gap-3">
        {kids.length > 1 && (
          <span className="text-[12px] font-semibold text-muted">Per kid</span>
        )}
        {!data &&
          [0, 1].map((i) => (
            <div key={i} className="bg-card rounded-2xl border border-border-hairline h-28 animate-pulse" />
          ))}
        {kids.map((a) => (
          <KidAllowanceCard
            key={a.kid_id}
            allowance={a}
            avatarColor={colorByKid[a.kid_id] ?? "amber"}
            currency={currency}
            disabled={!token}
            onSave={async (draft) => {
              await api.put(`/kids/${a.kid_id}/allowance`, token as string, {
                amount: Number(draft.amount),
                cadence: draft.cadence,
                payday: draft.payday,
                is_active: draft.is_active,
              });
              await afterWrite([a.kid_id]);
            }}
            onRemove={async () => {
              await api.delete(`/kids/${a.kid_id}/allowance`, token as string);
              await afterWrite([a.kid_id]);
            }}
            onError={(msg) => toast(msg, "error")}
          />
        ))}
        {data && kids.length === 0 && (
          <p className="text-center text-[13px] text-muted pt-2">
            No kids yet — add one in Settings first.
          </p>
        )}
      </div>
    </div>
  );
}

function EveryoneCard({
  currency,
  disabled,
  onApply,
}: {
  currency: string;
  disabled: boolean;
  onApply: (draft: Draft) => Promise<void>;
}) {
  const [draft, setDraft] = useState<Draft>({ amount: "", cadence: "weekly", payday: 0, is_active: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = Number(draft.amount) > 0;

  async function apply() {
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onApply(draft);
      setDraft({ amount: "", cadence: "weekly", payday: 0, is_active: true });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 bg-card rounded-2xl px-4 py-4 border border-border-hairline">
      <div className="flex flex-col gap-0.5">
        <h2 className="font-serif font-semibold text-[16px] text-emerald-dark">Set the same for everyone</h2>
        <p className="text-[12.5px] text-muted">Applies this allowance to every kid at once. You can still fine-tune each one below.</p>
      </div>
      <AmountField currency={currency} value={draft.amount} onChange={(amount) => setDraft((d) => ({ ...d, amount }))} />
      <CadenceField
        value={draft.cadence}
        onChange={(cadence) =>
          setDraft((d) => ({ ...d, cadence, payday: defaultPaydayFor(cadence, d.payday) }))
        }
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
    </div>
  );
}

function KidAllowanceCard({
  allowance,
  avatarColor,
  currency,
  disabled,
  onSave,
  onRemove,
  onError,
}: {
  allowance: AllowanceOut;
  avatarColor: string;
  currency: string;
  disabled: boolean;
  onSave: (draft: Draft) => Promise<void>;
  onRemove: () => Promise<void>;
  onError: (msg: string) => void;
}) {
  const server = useMemo(() => draftFromServer(allowance), [allowance]);
  const [draft, setDraft] = useState<Draft>(server);
  const [lastServer, setLastServer] = useState(server);
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState(false);

  // Adopt fresh server data (revalidation, another tab) unless the parent
  // has an unsaved edit in progress. React's "adjust state during render".
  const sig = JSON.stringify(server);
  const [lastSig, setLastSig] = useState(sig);
  if (sig !== lastSig) {
    setLastSig(sig);
    if (JSON.stringify(draft) === JSON.stringify(lastServer)) setDraft(server);
    setLastServer(server);
  }

  const dirty = JSON.stringify(draft) !== JSON.stringify(server);
  const valid = Number(draft.amount) > 0;

  async function save() {
    if (!valid || busy || !dirty) return;
    setBusy(true);
    try {
      await onSave(draft);
    } catch (e) {
      onError(e instanceof ApiError ? e.message : `Couldn't save ${allowance.kid_name}'s allowance`);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (removing) return;
    if (!confirm(`Stop ${allowance.kid_name}'s allowance? Past payments stay in their history.`)) return;
    setRemoving(true);
    try {
      await onRemove();
    } catch (e) {
      onError(e instanceof ApiError ? e.message : "Couldn't remove the allowance");
      setRemoving(false);
    }
  }

  const statusPill = !allowance.configured
    ? { label: "Not set", cls: "text-muted bg-tint-neutral" }
    : allowance.is_active
      ? { label: "Active", cls: "text-tint-dark bg-tint-emerald" }
      : { label: "Paused", cls: "text-brass-dark bg-tint-brass" };

  return (
    <div className="flex flex-col gap-3 bg-card rounded-2xl px-4 py-4 border border-border-hairline">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <Avatar name={allowance.kid_name} color={avatarColor} size={32} />
          <span className="font-semibold text-[14.5px] text-emerald-dark truncate">
            {allowance.kid_name}
          </span>
        </div>
        <span className={`text-[10px] font-semibold rounded-full px-1.5 py-0.5 shrink-0 ${statusPill.cls}`}>
          {statusPill.label}
        </span>
      </div>

      {allowance.configured && allowance.amount && allowance.cadence != null && allowance.payday != null && (
        <div className="text-[12.5px] text-muted leading-relaxed -mt-1">
          {formatMoney(allowance.amount, allowance.currency ?? currency)}{" "}
          {allowanceScheduleLabel(allowance.cadence, allowance.payday)}
          {allowance.is_active && allowance.next_payday && (
            <> · next {formatDate(allowance.next_payday)}</>
          )}
          <br />
          {allowance.last_paid_at
            ? `Last paid ${formatDate(allowance.last_paid_at)}`
            : "Not paid yet"}
        </div>
      )}

      <div className="flex flex-col gap-3 border-t border-border-hairline pt-3">
        <AmountField
          currency={currency}
          value={draft.amount}
          onChange={(amount) => setDraft((d) => ({ ...d, amount }))}
        />
        <CadenceField
          value={draft.cadence}
          onChange={(cadence) =>
            setDraft((d) => ({ ...d, cadence, payday: defaultPaydayFor(cadence, d.payday) }))
          }
        />
        <PaydayField
          cadence={draft.cadence}
          value={draft.payday}
          onChange={(payday) => setDraft((d) => ({ ...d, payday }))}
        />
        <label className="flex items-center justify-between gap-3 cursor-pointer">
          <span className="text-[13px] font-medium text-emerald-dark">
            {draft.is_active ? "Paying out" : "Paused"}
          </span>
          <input
            type="checkbox"
            checked={draft.is_active}
            onChange={(e) => setDraft((d) => ({ ...d, is_active: e.target.checked }))}
            className="w-5 h-5 accent-emerald cursor-pointer"
          />
        </label>

        <button
          type="button"
          disabled={disabled || !valid || busy || !dirty}
          onClick={save}
          className="bg-emerald text-white text-center min-h-11 py-[12px] rounded-xl text-[13.5px] font-semibold disabled:opacity-50 cursor-pointer"
        >
          {busy ? "Saving…" : allowance.configured ? "Save changes" : "Set allowance"}
        </button>
        {allowance.configured && (
          <button
            type="button"
            disabled={removing}
            onClick={remove}
            className="self-center text-[12.5px] font-semibold text-negative cursor-pointer disabled:opacity-50"
          >
            {removing ? "Removing…" : "Remove allowance"}
          </button>
        )}
      </div>
    </div>
  );
}
