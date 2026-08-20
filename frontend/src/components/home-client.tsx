"use client";

import { useState } from "react";
import Link from "next/link";
import { Logo } from "@/components/ui/logo";
import { KidCard } from "@/components/kid-card";
import { DebtSheet } from "@/components/debt-sheet";
import { AddKidSheet } from "@/components/add-kid-sheet";
import { formatMoney } from "@/lib/format";
import type { FamilyHome, KidSummary } from "@/lib/types";
import type { DebtTransactionType } from "@/lib/types";

export function HomeClient({ home }: { home: FamilyHome }) {
  const [debtTarget, setDebtTarget] = useState<{
    kid: KidSummary;
    direction: DebtTransactionType;
  } | null>(null);
  const [addKidOpen, setAddKidOpen] = useState(false);

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
        <div className="font-serif font-semibold text-[26px] text-emerald-dark leading-tight">
          You owe
        </div>
        <div className="font-serif font-semibold text-[34px] text-emerald">
          {formatMoney(home.total_owed, home.base_currency)}
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

        <button
          type="button"
          onClick={() => setAddKidOpen(true)}
          className="text-center p-3 text-muted font-semibold text-[13.5px] border-[1.5px] border-dashed border-border-hairline-strong rounded-2xl cursor-pointer"
        >
          + Add a kid
        </button>
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

      {addKidOpen && <AddKidSheet onClose={() => setAddKidOpen(false)} />}
    </div>
  );
}
