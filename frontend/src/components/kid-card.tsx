"use client";

import Link from "next/link";
import { Avatar } from "@/components/ui/avatar";
import { Money } from "@/components/ui/money";
import { formatMoney, formatPct } from "@/lib/format";
import type { KidSummary } from "@/lib/types";

export function KidCard({
  kid,
  currency,
  onAdd,
  onDeduct,
}: {
  kid: KidSummary;
  currency: string;
  onAdd: () => void;
  onDeduct: () => void;
}) {
  const dayChangePct = formatPct(kid.portfolio_day_change_pct);
  const isPositive = Number(kid.portfolio_day_change_pct ?? 0) >= 0;

  return (
    <div className="bg-card rounded-2xl p-4 border border-border-hairline flex flex-col gap-3">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2.5">
          <Avatar name={kid.name} color={kid.avatar_color} />
          <span className="font-semibold text-[15.5px] text-emerald-dark">{kid.name}</span>
        </div>
        <span className="font-serif font-semibold text-[19px] text-emerald">
          <Money amount={kid.cash_balance} currency={currency} />
        </span>
      </div>

      <div className="flex gap-2.5">
        <button
          type="button"
          onClick={onAdd}
          className="flex-1 min-h-11 bg-tint-emerald text-emerald text-center py-[11px] rounded-lg text-[13px] font-semibold cursor-pointer"
        >
          + Add
        </button>
        <button
          type="button"
          onClick={onDeduct}
          className="flex-1 min-h-11 bg-tint-negative text-negative text-center py-[11px] rounded-lg text-[13px] font-semibold border border-negative/20 cursor-pointer"
        >
          – Deduct
        </button>
      </div>

      <div className="flex justify-between items-center pt-2 border-t border-border-hairline">
        <div className="text-[13px] font-medium text-muted">
          Portfolio {formatMoney(kid.portfolio_value, currency)}
          {dayChangePct && (
            <span className={isPositive ? "text-positive" : "text-negative"}> {dayChangePct}</span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <Link href={`/home/kids/${kid.id}/history`} className="text-[13px] font-semibold text-muted-strong">
            History
          </Link>
          <Link href={`/home/kids/${kid.id}`} className="text-[13px] font-semibold text-emerald">
            Investments →
          </Link>
        </div>
      </div>
    </div>
  );
}
