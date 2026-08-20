"use client";

import { useState } from "react";
import { signOut, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Avatar } from "@/components/ui/avatar";
import { AddKidSheet } from "@/components/add-kid-sheet";
import { api, ApiError } from "@/lib/api";
import { SUPPORTED_CURRENCIES } from "@/lib/currencies";
import type { KidSummary } from "@/lib/types";

export function SettingsForm({
  currentCurrency,
  kids,
}: {
  currentCurrency: string;
  kids: KidSummary[];
}) {
  const { data: session } = useSession();
  const router = useRouter();
  const [currency, setCurrency] = useState(currentCurrency);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [addKidOpen, setAddKidOpen] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);

  async function handleSave() {
    if (!session?.backendToken) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await api.patch("/family/settings", session.backendToken, { base_currency: currency });
      setSaved(true);
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemoveKid(kid: KidSummary) {
    if (!session?.backendToken) return;
    if (!confirm(`Remove ${kid.name}? This deletes their balance and investment history too.`)) return;
    setRemovingId(kid.id);
    try {
      await api.delete(`/kids/${kid.id}`, session.backendToken);
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-8 px-5 pt-4 pb-8">
      <label className="flex flex-col gap-1.5">
        <span className="text-[12px] font-semibold text-muted">Family currency</span>
        <select
          value={currency}
          onChange={(e) => {
            setCurrency(e.target.value);
            setSaved(false);
          }}
          className="border border-border-hairline-strong rounded-[10px] px-3.5 py-3 text-[14.5px] text-emerald-dark outline-none focus:border-emerald bg-card"
        >
          {SUPPORTED_CURRENCIES.map((c) => (
            <option key={c.code} value={c.code}>
              {c.label}
            </option>
          ))}
        </select>

        {error && <p className="text-[13px] text-negative">{error}</p>}
        {saved && <p className="text-[13px] text-positive">Saved.</p>}

        <button
          type="button"
          disabled={saving || currency === currentCurrency}
          onClick={handleSave}
          className="bg-emerald text-white text-center py-[13px] rounded-xl text-[14px] font-semibold disabled:opacity-50 cursor-pointer mt-1"
        >
          {saving ? "Saving…" : "Save currency"}
        </button>
      </label>

      <div className="flex flex-col gap-2.5">
        <span className="text-[12px] font-semibold text-muted">Kids</span>

        {kids.map((kid) => (
          <div
            key={kid.id}
            className="bg-card rounded-2xl px-4 py-3 border border-border-hairline flex items-center justify-between"
          >
            <div className="flex items-center gap-2.5">
              <Avatar name={kid.name} color={kid.avatar_color} size={32} />
              <span className="font-semibold text-[14.5px] text-emerald-dark">{kid.name}</span>
            </div>
            <button
              type="button"
              disabled={removingId === kid.id}
              onClick={() => handleRemoveKid(kid)}
              className="text-[12.5px] font-semibold text-negative cursor-pointer disabled:opacity-50"
            >
              {removingId === kid.id ? "Removing…" : "Remove"}
            </button>
          </div>
        ))}

        <button
          type="button"
          onClick={() => setAddKidOpen(true)}
          className="text-center p-3 text-muted font-semibold text-[13.5px] border-[1.5px] border-dashed border-border-hairline-strong rounded-2xl cursor-pointer"
        >
          + Add a kid
        </button>
      </div>

      {addKidOpen && <AddKidSheet onClose={() => setAddKidOpen(false)} />}

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
                await signOut({ callbackUrl: "/" });
              } catch (e) {
                setError(e instanceof ApiError ? e.message : "Reset failed");
                setResetting(false);
              }
            }}
            className="text-center py-3 rounded-xl text-[13.5px] font-semibold border border-negative text-negative disabled:opacity-50 cursor-pointer"
          >
            {resetting ? "Resetting…" : "Reset to onboarding (dev only)"}
          </button>
        </div>
      )}
    </div>
  );
}
