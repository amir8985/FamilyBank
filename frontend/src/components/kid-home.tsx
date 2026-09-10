"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Avatar } from "@/components/ui/avatar";
import { Money } from "@/components/ui/money";
import { Skeleton } from "@/components/ui/skeleton";
import { useFamily, useKidLinks } from "@/lib/family-store";
import { useCachedResource } from "@/lib/use-cached-resource";
import { resetKidCaches } from "@/lib/kid-family-store";
import { api } from "@/lib/api";
import {
  allowanceScheduleLabel,
  formatDate,
  formatMoney,
  formatPct,
  formatSignedMoney,
} from "@/lib/format";
import type { AllowanceOut, PortfolioOut } from "@/lib/types";

export function KidHome() {
  const router = useRouter();
  const { home, token } = useFamily();
  const kid = home.kids[0]; // kid.id is the opaque public_id in the kid app
  const links = useKidLinks(kid.id);

  // Remember this kid so bare /kid comes straight back here (1 year).
  useEffect(() => {
    try {
      document.cookie = `kid_last=${kid.id}; path=/; max-age=31536000; samesite=lax`;
    } catch {
      /* private mode / cookies blocked — bare /kid just falls back to the first session */
    }
  }, [kid.id]);

  const portfolioRes = useCachedResource<PortfolioOut>(
    token ? `portfolio:${kid.id}` : null,
    () => api.get<PortfolioOut>(`/kids/${kid.id}/portfolio`, token as string),
    { ttlMs: 15_000 }
  );
  const allowanceRes = useCachedResource<AllowanceOut>(
    token ? `allowance:${kid.id}` : null,
    () => api.get<AllowanceOut>(`/kids/${kid.id}/allowance`, token as string),
    { ttlMs: 30_000 }
  );
  const allowance = allowanceRes.data;
  const p = portfolioRes.data;
  const currency = home.base_currency;

  const cash = p ? Number(p.cash_available) : Number(kid.cash_balance);
  const invested = p ? Number(p.holdings_value) : Number(kid.portfolio_value);
  const savings = p ? Number(p.savings_value) : 0;
  const dayChangePct = formatPct(p?.total_day_change_pct ?? null);
  const dayChangeAmount = p ? Number(p.total_day_change_amount) : 0;
  const up = dayChangeAmount >= 0;

  async function signOut() {
    await fetch("/kid/api/signout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ publicId: kid.id }),
    }).catch(() => {});
    try {
      document.cookie = "kid_last=; path=/; max-age=0";
    } catch {
      /* ignore */
    }
    resetKidCaches();
    router.replace("/kid/locked");
  }

  return (
    <div className="max-w-md mx-auto flex flex-col min-h-screen">
      <div className="pt-[58px] px-5 pb-2 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Avatar name={kid.name} color={kid.avatar_color} size={36} />
          <span className="font-serif font-semibold text-[19px] text-emerald-dark">
            Hi, {kid.name}
          </span>
        </div>
        <button
          type="button"
          onClick={signOut}
          className="text-[12.5px] font-semibold text-muted cursor-pointer"
        >
          Sign out
        </button>
      </div>

      <div className="px-5 pt-4 flex flex-col gap-3">
        <div className="bg-card rounded-2xl p-4 border border-border-hairline shadow-[0_1px_3px_rgba(0,0,0,.06)]">
          <div className="text-[13px] font-medium text-muted">Your money</div>
          <div className="font-serif font-semibold text-[34px] text-emerald leading-tight">
            <Money amount={cash} currency={currency} />
          </div>
          <div className="text-[12px] text-muted mt-0.5">
            This is what your parent is keeping for you.
          </div>
        </div>

        <div className="bg-emerald rounded-2xl p-4 shadow-[0_1px_3px_rgba(0,0,0,.1)]">
          <div className="flex items-baseline justify-between">
            <div className="text-[13px] font-semibold text-[oklch(85%_0.02_155)]">Your investments</div>
            {invested > 0 && dayChangePct && (
              <div
                className={`text-[12.5px] font-semibold ${up ? "text-[oklch(80%_0.13_150)]" : "text-[oklch(72%_0.13_25)]"}`}
              >
                {dayChangePct}
              </div>
            )}
          </div>
          {p ? (
            <>
              <div className="font-serif font-semibold text-[30px] text-white leading-tight">
                <Money amount={invested} currency={currency} />
              </div>
              {invested > 0 && dayChangePct ? (
                <div
                  className={`text-[12.5px] font-medium mt-0.5 ${up ? "text-[oklch(80%_0.13_150)]" : "text-[oklch(72%_0.13_25)]"}`}
                >
                  {up ? "▲" : "▼"} {formatSignedMoney(dayChangeAmount, currency)} today
                </div>
              ) : (
                <div className="text-[12.5px] font-medium mt-0.5 text-[oklch(78%_0.02_155)]">
                  Nothing invested yet — tap below to start.
                </div>
              )}
            </>
          ) : (
            <Skeleton className="h-8 w-32 mt-1" />
          )}
        </div>

        {savings > 0 && (
          <div className="bg-card rounded-2xl px-4 py-3 border border-border-hairline flex items-center justify-between">
            <span className="text-[13px] font-medium text-muted-strong">In savings</span>
            <span className="font-semibold text-[15px] text-emerald-dark">
              {formatMoney(savings, currency)}
            </span>
          </div>
        )}

        {allowance?.configured &&
          allowance.amount &&
          allowance.cadence != null &&
          allowance.payday != null && (
            <div className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex flex-col gap-1">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-medium text-muted-strong">Your allowance</span>
                <span className="font-semibold text-[15px] text-emerald-dark">
                  {formatMoney(allowance.amount, allowance.currency ?? currency)}
                </span>
              </div>
              <div className="text-[12px] text-muted">
                {allowanceScheduleLabel(allowance.cadence, allowance.payday)}
                {" · "}
                {allowance.recent_payments.length > 0
                  ? `last paid ${formatDate(allowance.recent_payments[0].paid_at)}`
                  : allowance.next_payday
                    ? `first payment ${formatDate(allowance.next_payday)}`
                    : ""}
              </div>
            </div>
          )}
      </div>

      <div className="flex-1 px-5 pt-4 pb-6 flex flex-col gap-2.5">
        <Link
          href={links.portfolio}
          className="bg-emerald text-white text-center min-h-11 py-[15px] rounded-xl text-[15px] font-semibold"
        >
          Portfolio
        </Link>
        <Link
          href={`${links.pagePrefix}/history`}
          className="text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold border border-border-hairline-strong text-emerald-dark"
        >
          My balance history
        </Link>
      </div>
    </div>
  );
}
