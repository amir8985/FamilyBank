"use client";

import { useState } from "react";
import { signOut, useSession } from "next-auth/react";
import Link from "next/link";
import { Avatar } from "@/components/ui/avatar";
import { AddKidSheet } from "@/components/add-kid-sheet";
import { AttachChildSheet } from "@/components/attach-child-sheet";
import { CurrencyChangeSheet } from "@/components/currency-change-sheet";
import { useFamily, resetClientCaches } from "@/lib/family-store";
import { useCachedResource } from "@/lib/use-cached-resource";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { SUPPORTED_CURRENCIES } from "@/lib/currencies";
import type { FamilyAllowancesOut, FamilySettings, KidSummary, SavingsPlanOut } from "@/lib/types";

function StatusPill({ on }: { on: boolean | null }) {
  if (on === null) return null;
  return on ? (
    <span className="text-[10px] font-semibold rounded-full px-1.5 py-0.5 text-tint-dark bg-tint-emerald shrink-0">
      Active
    </span>
  ) : (
    <span className="text-[10px] font-semibold rounded-full px-1.5 py-0.5 text-brass-dark bg-tint-brass shrink-0">
      Not set up
    </span>
  );
}

export function SettingsForm() {
  const { data: session } = useSession();
  const { home, removeKidOptimistic, refreshHome } = useFamily();
  const toast = useToast();
  const currentCurrency = home.base_currency;
  const kids = home.kids;
  const token = session?.backendToken ?? null;

  const { data: allowances } = useCachedResource<FamilyAllowancesOut>(
    token ? "family-allowances" : null,
    () => api.get<FamilyAllowancesOut>("/family/allowances", token as string),
    { ttlMs: 60_000 }
  );
  const { data: familySettings } = useCachedResource<FamilySettings>(
    token ? "family-settings" : null,
    () => api.get<FamilySettings>("/family/settings", token as string),
    { ttlMs: 5 * 60_000 }
  );
  const { data: savingsPlans } = useCachedResource<SavingsPlanOut[]>(
    token ? "savings-plans" : null,
    () => api.get<SavingsPlanOut[]>("/family/savings-plans", token as string),
    { ttlMs: 60_000 }
  );

  const allowanceOn = allowances ? allowances.kids.some((k) => k.configured) : null;
  const investingOn =
    familySettings && savingsPlans
      ? familySettings.boost_buffer_rate !== null || savingsPlans.some((p) => p.is_active)
      : null;

  const [currency, setCurrency] = useState(currentCurrency);
  const [changeTarget, setChangeTarget] = useState<string | null>(null);
  const [addKidOpen, setAddKidOpen] = useState(false);
  const [attachKid, setAttachKid] = useState<KidSummary | null>(null);
  const [resetting, setResetting] = useState(false);

  function handleRemoveKid(kid: KidSummary) {
    if (!session?.backendToken) return;
    if (!confirm(`Remove ${kid.name}? This deletes their balance and investment history too.`)) return;

    const token = session.backendToken;
    const rollback = removeKidOptimistic(kid.id);

    api
      .delete(`/kids/${kid.id}`, token)
      .then(() => refreshHome())
      .catch((e) => {
        rollback();
        const msg =
          e instanceof ApiError && e.status < 500
            ? e.message
            : `Couldn't remove ${kid.name} — they're back in the list.`;
        toast(msg, "error");
      });
  }

  return (
    <div className="flex flex-col gap-8 px-5 pt-4 pb-8">
      <label className="flex flex-col gap-1.5">
        <span className="text-[12px] font-semibold text-muted">Family currency</span>
        <select
          value={currency}
          onChange={(e) => setCurrency(e.target.value)}
          className="border border-border-hairline-strong rounded-[10px] px-3.5 py-3 text-[14.5px] text-emerald-dark outline-none focus:border-emerald bg-card"
        >
          {SUPPORTED_CURRENCIES.map((c) => (
            <option key={c.code} value={c.code}>
              {c.label}
            </option>
          ))}
        </select>

        <button
          type="button"
          disabled={currency === currentCurrency}
          onClick={() => setChangeTarget(currency)}
          className="bg-emerald text-white text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold disabled:opacity-50 cursor-pointer mt-1"
        >
          Change currency
        </button>
      </label>

      <Link
        href="/home/settings/allowance"
        className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex items-center justify-between gap-2"
      >
        <span className="flex flex-col min-w-0">
          <span className="font-semibold text-[14.5px] text-emerald-dark">Allowance</span>
          <span className="text-[12px] text-muted">Recurring pocket money, weekly or monthly</span>
        </span>
        <span className="flex items-center gap-2 shrink-0">
          <StatusPill on={allowanceOn} />
          <span className="text-emerald text-lg">›</span>
        </span>
      </Link>

      <Link
        href="/home/settings/investing"
        className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex items-center justify-between gap-2"
      >
        <span className="flex flex-col min-w-0">
          <span className="font-semibold text-[14.5px] text-emerald-dark">
            Advanced investing &amp; savings
          </span>
          <span className="text-[12px] text-muted">Stock boost and savings plans</span>
        </span>
        <span className="flex items-center gap-2 shrink-0">
          <StatusPill on={investingOn} />
          <span className="text-emerald text-lg">›</span>
        </span>
      </Link>

      <div className="flex flex-col gap-2.5">
        <span className="text-[12px] font-semibold text-muted">Kids</span>

        {kids.map((kid) => {
          const pending = kid.id.startsWith("temp-");
          return (
            <div
              key={kid.id}
              className="bg-card rounded-2xl border border-border-hairline overflow-hidden"
            >
              <div className="px-4 py-3 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2.5 min-w-0">
                  <Avatar name={kid.name} color={kid.avatar_color} size={32} />
                  <span className="font-semibold text-[14.5px] text-emerald-dark truncate">
                    {kid.name}
                  </span>
                </div>
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => handleRemoveKid(kid)}
                  className="text-[12px] font-semibold text-negative cursor-pointer disabled:opacity-40 shrink-0"
                >
                  {pending ? "Saving…" : "Remove"}
                </button>
              </div>
              <button
                type="button"
                disabled={pending}
                onClick={() => setAttachKid(kid)}
                className="w-full px-4 py-3 border-t border-border-hairline flex items-center justify-between text-emerald font-semibold text-[13.5px] cursor-pointer disabled:opacity-40"
              >
                <span>Link a device</span>
                <span className="text-lg">›</span>
              </button>
            </div>
          );
        })}

        <button
          type="button"
          onClick={() => setAddKidOpen(true)}
          className="text-center min-h-11 p-3 text-muted font-semibold text-[13.5px] border-[1.5px] border-dashed border-border-hairline-strong rounded-2xl cursor-pointer"
        >
          + Add a kid
        </button>
      </div>

      {addKidOpen && <AddKidSheet onClose={() => setAddKidOpen(false)} />}

      {attachKid && (
        <AttachChildSheet
          kidId={attachKid.id}
          kidName={attachKid.name}
          onClose={() => setAttachKid(null)}
        />
      )}

      {changeTarget && (
        <CurrencyChangeSheet
          fromCurrency={currentCurrency}
          toCurrency={changeTarget}
          onClose={() => setChangeTarget(null)}
        />
      )}

      {process.env.NODE_ENV === "development" && (
        <div className="flex flex-col gap-2 pt-6 border-t border-border-hairline-strong">
          <span className="text-[12px] font-semibold text-muted">Dev tools</span>
          <button
            type="button"
            disabled={resetting}
            onClick={async () => {
              if (!session?.backendToken) return;
              if (!confirm("Wipe this family back to a fresh, un-onboarded state and sign out?")) return;
              setResetting(true);
              try {
                await api.post("/internal/dev-reset", session.backendToken);
                resetClientCaches();
                await signOut({ callbackUrl: "/" });
              } catch (e) {
                toast(e instanceof ApiError ? e.message : "Reset failed", "error");
                setResetting(false);
              }
            }}
            className="text-center min-h-11 py-3 rounded-xl text-[13.5px] font-semibold border border-negative text-negative disabled:opacity-50 cursor-pointer"
          >
            {resetting ? "Resetting…" : "Reset to onboarding (dev only)"}
          </button>
        </div>
      )}
    </div>
  );
}
