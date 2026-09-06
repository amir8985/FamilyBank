"use client";

import { useState } from "react";
import Link from "next/link";
import { Logo } from "@/components/ui/logo";
import { KidCard } from "@/components/kid-card";
import { DebtSheet } from "@/components/debt-sheet";
import { Money } from "@/components/ui/money";
import { formatMoney } from "@/lib/format";
import type { FamilyHome, KidSummary } from "@/lib/types";
import type { DebtTransactionType } from "@/lib/types";

export function HomeClient({ home }: { home: FamilyHome }) {
  const [debtTarget, setDebtTarget] = useState<{
    kid: KidSummary;
    direction: DebtTransactionType;
  } | null>(null);

  return (
    <div className="max-w-md mx-auto flex flex-col min-h-screen">
      <div className="pt-[58px] px-5 pb-2 flex items-center justify-between">
        <Logo />
        <Link
          href="/home/settings"
          aria-label="Settings"
          className="w-8 h-8 rounded-full bg-tint-icon flex items-center justify-center"
        >
          <span className="w-3.5 h-3.5 rounded-full border-2 border-muted-strong" />
        </Link>
      </div>

      <div className="px-5 pt-4 pb-1.5">
        <div className="bg-card rounded-2xl p-4 border border-border-hairline shadow-[0_1px_3px_rgba(0,0,0,.06)]">
          <div className="font-serif font-semibold text-[26px] text-emerald-dark leading-tight">
            Total balance
          </div>
          <div className="font-serif font-semibold text-[34px] text-emerald">
            <Money amount={home.total_owed} currency={home.base_currency} />
          </div>
          {Number(home.total_invested) > 0 && (
            <div className="text-[13px] font-medium text-muted mt-0.5">
              + {formatMoney(home.total_invested, home.base_currency)} in investments
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 px-5 pt-3.5 pb-6 flex flex-col gap-3">
        {home.kids.map((kid) => (
          <KidCard
            key={kid.id}
            kid={kid}
            currency={home.base_currency}
            onAdd={() => setDebtTarget({ kid, direction: "add" })}
            onDeduct={() => setDebtTarget({ kid, direction: "deduct" })}
          />
        ))}

        {home.kids.length === 0 && (
          <p className="text-center text-[13px] text-muted pt-4">
            No kids yet —{" "}
            <Link href="/home/settings" className="font-semibold text-emerald">
              add one in Settings
            </Link>
            .
          </p>
        )}
      </div>

      {debtTarget && (
        <DebtSheet
          onClose={() => setDebtTarget(null)}
          kidId={debtTarget.kid.id}
          kidName={debtTarget.kid.name}
          currentBalance={Number(debtTarget.kid.cash_balance)}
          currency={home.base_currency}
          initialDirection={debtTarget.direction}
        />
      )}
    </div>
  );
}
