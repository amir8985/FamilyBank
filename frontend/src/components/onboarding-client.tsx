"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Logo } from "@/components/ui/logo";
import { api, ApiError } from "@/lib/api";
import { SUPPORTED_CURRENCIES } from "@/lib/currencies";
import type { FamilySettings } from "@/lib/types";

export function OnboardingClient() {
  const { data: session } = useSession();
  const router = useRouter();
  const [currency, setCurrency] = useState("USD");
  const [kidNames, setKidNames] = useState<string[]>([""]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateKidName(index: number, value: string) {
    setKidNames((prev) => prev.map((n, i) => (i === index ? value : n)));
  }

  function addKidRow() {
    setKidNames((prev) => [...prev, ""]);
  }

  function removeKidRow(index: number) {
    setKidNames((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit() {
    if (!session?.backendToken) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post<FamilySettings>("/family/onboarding", session.backendToken, {
        base_currency: currency,
        kid_names: kidNames.map((n) => n.trim()).filter(Boolean),
      });
      router.push("/home");
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col px-5 pt-16 pb-10">
      <Logo />

      <div className="mt-10 mb-8">
        <h1 className="font-serif font-semibold text-[26px] text-emerald-dark leading-tight">
          Let&apos;s set up your family
        </h1>
        <p className="text-[14.5px] text-muted mt-1.5">
          Just two quick things — you can always change these later in Settings.
        </p>
      </div>

      <div className="flex flex-col gap-7 flex-1">
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
        </label>

        <div className="flex flex-col gap-2.5">
          <span className="text-[12px] font-semibold text-muted">
            Your kids <span className="font-normal">(optional — add them now or later)</span>
          </span>
          {kidNames.map((name, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                value={name}
                onChange={(e) => updateKidName(i, e.target.value)}
                placeholder="e.g. Maya"
                maxLength={60}
                className="flex-1 border border-border-hairline-strong rounded-[10px] px-3.5 py-3 text-[14.5px] text-emerald-dark outline-none focus:border-emerald"
              />
              {kidNames.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeKidRow(i)}
                  aria-label="Remove"
                  className="w-9 h-9 flex items-center justify-center text-muted text-lg cursor-pointer"
                >
                  ×
                </button>
              )}
            </div>
          ))}
          <button
            type="button"
            onClick={addKidRow}
            className="text-left text-[13px] font-semibold text-emerald cursor-pointer"
          >
            + Add another kid
          </button>
        </div>
      </div>

      {error && <p className="text-[13px] text-negative mb-2">{error}</p>}

      <button
        type="button"
        disabled={submitting}
        onClick={handleSubmit}
        className="bg-emerald text-white text-center min-h-11 py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer mt-2"
      >
        {submitting ? "Setting up…" : "Continue"}
      </button>
    </div>
  );
}
