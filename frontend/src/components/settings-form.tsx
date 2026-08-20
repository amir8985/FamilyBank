"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

const CURRENCIES = [
  { code: "ILS", label: "₪ Israeli Shekel (ILS)" },
  { code: "USD", label: "$ US Dollar (USD)" },
  { code: "EUR", label: "€ Euro (EUR)" },
];

export function SettingsForm({ currentCurrency }: { currentCurrency: string }) {
  const { data: session } = useSession();
  const router = useRouter();
  const [currency, setCurrency] = useState(currentCurrency);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

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

  return (
    <div className="flex flex-col gap-4 px-5 pt-4">
      <label className="flex flex-col gap-1.5">
        <span className="text-[12px] font-semibold text-muted">Family base currency</span>
        <select
          value={currency}
          onChange={(e) => {
            setCurrency(e.target.value);
            setSaved(false);
          }}
          className="border border-border-hairline-strong rounded-[10px] px-3.5 py-3 text-[14.5px] text-emerald-dark outline-none focus:border-emerald bg-card"
        >
          {CURRENCIES.map((c) => (
            <option key={c.code} value={c.code}>
              {c.label}
            </option>
          ))}
        </select>
      </label>

      {error && <p className="text-[13px] text-negative">{error}</p>}
      {saved && <p className="text-[13px] text-positive">Saved.</p>}

      <button
        type="button"
        disabled={saving || currency === currentCurrency}
        onClick={handleSave}
        className="bg-emerald text-white text-center py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        {saving ? "Saving…" : "Save"}
      </button>
    </div>
  );
}
