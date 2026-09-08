"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { SellAndRebuySheet } from "@/components/sell-and-rebuy-sheet";
import { useFamily } from "@/lib/family-store";
import { clearResourceCache, invalidateResource } from "@/lib/use-cached-resource";

const RECOMMENDED_RATE = 3.0;
const DAYS_PER_MONTH = 30.44;
const EXAMPLE_INVESTMENT = 50;
// The S&P 500's actual long-run average is close to 0.8%/month (~10%/year
// nominal, including dividends) — rounded to a clean, still-realistic 1%
// rather than the punchier-but-misleading 2% an earlier draft used.
const EXAMPLE_MONTHLY_GAIN_PCT = 1;
// Illustrative — "about two-thirds of the days that month were up" — so
// the example can show that the boost only applies to that fraction of
// the nominal rate, not the whole thing, which is what actually happens.
const EXAMPLE_UP_DAY_FRACTION = 2 / 3;
// A round anchor for the "this is a monthly rate, and monthly rates
// compound fast" callout below — real savings accounts quote a rate per
// *year*, so a parent needs a concrete number to feel how different
// a monthly rate actually is, not just be told it compounds.
const RATE_CONTEXT_AMOUNT = 1000;

function clampRate(value: number): number {
  return Math.min(100, Math.max(0, Math.round(value * 10) / 10));
}

export function BoostSettingsForm({ currentRate }: { currentRate: string | null }) {
  const { data: session } = useSession();
  const router = useRouter();
  const { refreshHome } = useFamily();

  const isOn = currentRate !== null;
  const [enabled, setEnabled] = useState(isOn);
  const [rate, setRate] = useState(isOn ? Number(currentRate) : RECOMMENDED_RATE);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Whether the last save failed specifically because kids still hold
  // stock — only then does the "sell everything and rebuy" offer make
  // sense (see routes_family.py's 409).
  const [blockedByHoldings, setBlockedByHoldings] = useState(false);
  const [sellingAndRebuying, setSellingAndRebuying] = useState(false);
  const [rebuySheetOpen, setRebuySheetOpen] = useState(false);

  const savedRate = isOn ? Number(currentRate) : null;
  const pendingRate = enabled ? rate : null;
  const isUnchanged = pendingRate === savedRate;

  const perDayPct = rate / DAYS_PER_MONTH;
  // Always illustrates the recommended rate, not whatever the parent
  // currently has the stepper set to — keeps the example a stable,
  // memorable anchor rather than a number that shifts as they fiddle
  // with the stepper. Only the up-day fraction of the nominal rate
  // actually applies (see boost_service._walk on the backend) — the
  // example shows that explicitly rather than implying the full rate
  // always lands.
  const effectiveBoostPct = RECOMMENDED_RATE * EXAMPLE_UP_DAY_FRACTION;
  const withoutBoost = EXAMPLE_INVESTMENT * (1 + EXAMPLE_MONTHLY_GAIN_PCT / 100);
  const withBoost = EXAMPLE_INVESTMENT * (1 + EXAMPLE_MONTHLY_GAIN_PCT / 100 + effectiveBoostPct / 100);
  const boostContribution = withBoost - withoutBoost;

  // Tracks the currently-selected rate (not the fixed recommendation) —
  // the whole point is to show the parent what *their* number means.
  const yearlyBoostOnRateContext = RATE_CONTEXT_AMOUNT * (Math.pow(1 + rate / 100, 12) - 1);

  async function handleSave() {
    if (!session?.backendToken) return;
    setSaving(true);
    setError(null);
    setBlockedByHoldings(false);
    try {
      await api.patch("/family/settings/boost-buffer-rate", session.backendToken, {
        rate: enabled ? rate : null,
      });
      invalidateResource("family-settings");
      // Saving is the natural end of this screen's job — send the parent
      // back to Settings rather than leaving them stranded here (per
      // user feedback: a way back out, without adding another UI element).
      router.push("/home/settings");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError("Every kid must sell all their stock before this can be changed — buy/sell it back afterward at the new setting.");
        setBlockedByHoldings(true);
      } else {
        setError(e instanceof ApiError ? e.message : "Something went wrong");
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleConfirmSellAndRebuy() {
    if (!session?.backendToken) return;
    setSellingAndRebuying(true);
    setError(null);
    try {
      await api.post("/family/settings/boost-buffer-rate/sell-and-rebuy", session.backendToken, {
        rate: enabled ? rate : null,
      });
      // Sell-and-rebuy touches every kid's holdings and cash — the
      // simplest safe reconcile is to drop all per-kid caches and pull
      // a fresh home.
      clearResourceCache();
      refreshHome();
      router.push("/home/settings");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
      setRebuySheetOpen(false);
    } finally {
      setSellingAndRebuying(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 px-5 pt-4 pb-8">
      <label className="flex items-center justify-between bg-card rounded-2xl px-4 py-3.5 border border-border-hairline cursor-pointer">
        <span className="font-semibold text-[14.5px] text-emerald-dark">Stock boost active</span>
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
          className="w-5 h-5 accent-emerald cursor-pointer"
        />
      </label>

      {/* Explanation, rate picker, and example stay visible regardless of
          the toggle — a parent should be able to read what this does and
          preview a rate before deciding to turn it on, not only after. */}
      <div className="flex flex-col gap-2.5">
        <span className="text-[12px] font-semibold text-muted">Monthly boost rate</span>
        <div className="flex items-center gap-3 bg-card rounded-2xl px-4 py-3.5 border border-border-hairline">
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
        <p className="text-[12px] text-muted">
          We suggest starting at {RECOMMENDED_RATE.toFixed(1)}%/month.
        </p>
        <p className="text-[11.5px] text-muted/80">
          That&apos;s roughly {perDayPct.toFixed(2)}% added on a day the stock is rising.
        </p>
      </div>

      <p className="text-[13.5px] text-muted leading-relaxed">
        The idea behind the stock boost is to make small amounts move enough that a kid actually
        notices. Index funds usually beat savings interest on their own anyway, so if you offer
        both, set this at least 1% above your savings rate.
      </p>
      <p className="text-[13.5px] text-muted leading-relaxed">
        Here&apos;s the idea: every time the stock rises, your kid&apos;s holding gets a small
        bonus on top of the real gain — never on a day it falls, so a bad day is exactly as bad
        as it&apos;s always been.
      </p>
      <p className="text-[13.5px] text-muted leading-relaxed">
        Keep in mind this is a monthly rate, not yearly — real savings accounts are usually
        quoted per year. At {rate.toFixed(1)}%/month, {formatMoney(RATE_CONTEXT_AMOUNT, "USD")}{" "}
        held for a year earns about {formatMoney(yearlyBoostOnRateContext, "USD")} from the boost
        alone. Worth knowing before you settle on a number.
      </p>

      <div className="bg-tint-emerald rounded-2xl px-4 py-3.5 flex flex-col gap-1.5">
        <span className="text-[12px] font-semibold text-tint-dark">Example</span>
        <p className="text-[13px] text-tint-dark leading-relaxed">
          Say your kid puts {formatMoney(EXAMPLE_INVESTMENT, "USD")} into an S&amp;P 500 fund. A
          realistic month lands around {EXAMPLE_MONTHLY_GAIN_PCT}% overall, but the boost only
          counts on days it actually rose. If two-thirds of those days were up, about two-thirds
          of your {RECOMMENDED_RATE.toFixed(1)}% rate applies too: roughly{" "}
          {effectiveBoostPct.toFixed(1)}%. Instead of {formatMoney(withoutBoost, "USD")}, they end
          up with about <strong>{formatMoney(withBoost, "USD")}</strong> — an extra{" "}
          {formatMoney(boostContribution, "USD")} from the boost.
        </p>
      </div>

      {error && <p className="text-[13px] text-negative">{error}</p>}
      {blockedByHoldings && (
        <button
          type="button"
          onClick={() => setRebuySheetOpen(true)}
          className="text-left text-[13px] font-semibold text-negative cursor-pointer -mt-3"
        >
          ⚠ Sell everything and rebuy with the new boost
        </button>
      )}

      <button
        type="button"
        disabled={saving || isUnchanged}
        onClick={handleSave}
        className="bg-emerald text-white text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        {saving ? "Saving…" : isUnchanged ? "No changes to save" : enabled ? "Save boost" : "Turn boost off"}
      </button>

      {rebuySheetOpen && (
        <SellAndRebuySheet
          targetLabel={enabled ? `${rate.toFixed(1)}%/month` : "no boost"}
          confirming={sellingAndRebuying}
          onConfirm={handleConfirmSellAndRebuy}
          onClose={() => setRebuySheetOpen(false)}
        />
      )}
    </div>
  );
}
