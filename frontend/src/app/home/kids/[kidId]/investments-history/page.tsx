"use client";

import { use } from "react";
import { useSession } from "next-auth/react";
import { useFamily } from "@/lib/family-store";
import { useCachedResource } from "@/lib/use-cached-resource";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { TickerBadge } from "@/components/ui/ticker-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime, formatMoney, trimUnits } from "@/lib/format";
import type { InvestmentTransactionOut } from "@/lib/types";

export default function KidInvestmentHistoryPage({
  params,
}: {
  params: Promise<{ kidId: string }>;
}) {
  const { kidId } = use(params);
  const { data: session } = useSession();
  const { home } = useFamily();
  const token = session?.backendToken ?? null;
  const kid = home.kids.find((k) => k.id === kidId);

  const { data: transactions, error } = useCachedResource<InvestmentTransactionOut[]>(
    token ? `investment-transactions:${kidId}` : null,
    () =>
      api.get<InvestmentTransactionOut[]>(
        `/kids/${kidId}/investment-transactions`,
        token as string
      ),
    { ttlMs: 15_000 }
  );

  // Fetch failed with nothing cached — route to the segment error boundary.
  if (error && !transactions) throw error;

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader
        title={kid ? `${kid.name}'s Investment History` : "Investment History"}
        backHref={`/home/kids/${kidId}`}
      />

      <div className="flex-1 px-5 pt-3 pb-6 flex flex-col gap-2.5">
        {!transactions &&
          [0, 1, 2].map((i) => (
            <div
              key={i}
              className="bg-card rounded-2xl px-4 py-3 border border-border-hairline flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <Skeleton className="w-9 h-9 rounded-full" />
                <Skeleton className="h-4 w-28" />
              </div>
              <Skeleton className="h-4 w-16" />
            </div>
          ))}

        {transactions && transactions.length === 0 && (
          <p className="text-center text-[13px] text-muted pt-4">No buys or sells yet.</p>
        )}

        {transactions?.map((t) => {
          // Native currency — investment_transactions store the price
          // exactly as it was at the time, unconverted (architecture §1).
          const total = (Number(t.price) * Number(t.units)).toFixed(2);
          return (
            <div
              key={t.id}
              className="bg-card rounded-2xl px-4 py-3 border border-border-hairline flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <TickerBadge symbol={t.symbol} size={36} />
                <div>
                  <div className="font-semibold text-[14px] text-emerald-dark capitalize">
                    {t.type === "buy" ? "Bought" : "Sold"} {trimUnits(t.units)} units
                  </div>
                  <div className="text-[11px] text-muted mt-0.5">{formatDateTime(t.created_at)}</div>
                </div>
              </div>
              <div
                className={`font-semibold text-[14px] ${t.type === "buy" ? "text-emerald-dark" : "text-positive"}`}
              >
                {formatMoney(total, t.price_currency)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
