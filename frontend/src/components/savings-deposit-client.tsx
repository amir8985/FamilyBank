"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/ui/page-header";
import { Money } from "@/components/ui/money";
import { LotChart } from "@/components/ui/lot-chart";
import { SavingsKindBadge } from "@/components/ui/savings-badge";
import { api, ApiError } from "@/lib/api";
import { formatMoney, formatDateTime } from "@/lib/format";
import type { SavingsDepositDetailOut } from "@/lib/types";

function lockStatus(deposit: SavingsDepositDetailOut): { locked: boolean; text: string } {
  if (!deposit.is_locked) return { locked: false, text: "Flexible — withdraw any time" };
  if (deposit.is_matured || !deposit.matures_at) {
    return { locked: false, text: "Unlocked — the term is up, still earning the same rate" };
  }
  const days = Math.max(1, Math.ceil((new Date(deposit.matures_at).getTime() - Date.now()) / 86_400_000));
  const when = new Date(deposit.matures_at).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
  const months = Math.round(days / 30.44);
  const left = days < 31 ? `${days} day${days === 1 ? "" : "s"}` : `${months} month${months === 1 ? "" : "s"}`;
  return { locked: true, text: `Locked until ${when} · ${left} left` };
}

export function SavingsDepositClient({
  kidId,
  deposit,
}: {
  kidId: string;
  deposit: SavingsDepositDetailOut;
}) {
  const { data: session } = useSession();
  const router = useRouter();
  const [withdrawing, setWithdrawing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currency = deposit.currency;
  const value = Number(deposit.current_value);
  const interest = Number(deposit.accrued_interest);
  const status = lockStatus(deposit);

  async function handleWithdraw() {
    if (!session?.backendToken) return;
    if (!confirm(`Withdraw ${formatMoney(value, currency)} from ${deposit.plan_name} back to cash?`)) return;
    setWithdrawing(true);
    setError(null);
    try {
      await api.post(`/kids/${kidId}/savings/${deposit.deposit_id}/withdraw`, session.backendToken);
      router.push(`/home/kids/${kidId}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
      setWithdrawing(false);
    }
  }

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title={deposit.plan_name} backHref={`/home/kids/${kidId}`} />

      <div className="px-5 pt-3.5 flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <SavingsKindBadge
            locked={deposit.is_locked && !deposit.is_matured}
            label={deposit.is_locked ? (deposit.is_matured ? "Unlocked" : "Locked") : "Flexible"}
          />
          <div className="text-[12.5px] text-muted">
            {Number(deposit.monthly_rate).toFixed(1)}%/month · ≈ {Number(deposit.annual_rate).toFixed(1)}%/year ·
            opened {formatDateTime(deposit.opened_at)}
          </div>
        </div>

        <div className="text-center py-[18px] bg-card border border-border-hairline rounded-2xl">
          <div className="font-serif font-semibold text-[32px] text-emerald">
            <Money amount={value} currency={currency} />
          </div>
          {interest > 0 && (
            <div className="text-[13.5px] font-semibold mt-1 text-positive">
              +{formatMoney(interest, currency)} interest so far
            </div>
          )}
        </div>

        <LotChart series={deposit.series} currency={deposit.series_currency} />

        <div className="flex justify-between text-[13.5px] text-muted px-0.5">
          <span>Put in</span>
          <span className="font-semibold text-emerald-dark">{formatMoney(deposit.principal, currency)}</span>
        </div>

        <div
          className={`text-center text-[12.5px] rounded-2xl py-3 ${
            status.locked ? "bg-tint-brass text-brass-dark" : "bg-cream text-muted"
          }`}
        >
          {deposit.is_open ? status.text : `Withdrawn ${deposit.closed_at ? formatDateTime(deposit.closed_at) : ""}`}
        </div>

        {error && <p className="text-[13px] text-negative">{error}</p>}

        {deposit.is_open &&
          (status.locked ? (
            <button
              type="button"
              disabled
              className="text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold bg-tint-neutral text-muted"
            >
              Locked for now
            </button>
          ) : (
            <button
              type="button"
              disabled={withdrawing}
              onClick={handleWithdraw}
              className="text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold bg-negative text-white cursor-pointer disabled:opacity-50"
            >
              {withdrawing ? "Withdrawing…" : `Withdraw ${formatMoney(value, currency)}`}
            </button>
          ))}
      </div>
    </div>
  );
}
