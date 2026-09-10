"use client";

import { use } from "react";
import { useFamily, useKidLinks } from "@/lib/family-store";
import { useCachedResource } from "@/lib/use-cached-resource";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { DebtTransactionOut } from "@/lib/types";

export default function KidHistoryPage({
  params,
}: {
  params: Promise<{ kidId: string }>;
}) {
  const { kidId } = use(params);
  const { home, token } = useFamily();
  const links = useKidLinks(kidId);
  const kid = home.kids.find((k) => k.id === kidId);

  const { data: transactions, error } = useCachedResource<DebtTransactionOut[]>(
    token ? `debt:${kidId}` : null,
    () => api.get<DebtTransactionOut[]>(`/kids/${kidId}/debt`, token as string),
    { ttlMs: 15_000 }
  );

  // Fetch failed with nothing cached — route to the segment error
  // boundary rather than spinning forever.
  if (error && !transactions) throw error;

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title={kid ? `${kid.name}'s History` : "History"} backHref={links.home} />

      <div className="flex-1 px-5 pt-3 pb-6 flex flex-col gap-2.5">
        {!transactions &&
          [0, 1, 2].map((i) => (
            <div
              key={i}
              className="bg-card rounded-2xl px-4 py-3 border border-border-hairline flex items-center justify-between"
            >
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-16" />
            </div>
          ))}

        {transactions && transactions.length === 0 && (
          <p className="text-center text-[13px] text-muted pt-4">No balance changes yet.</p>
        )}

        {transactions?.map((t) => {
          const label = t.is_adjustment
            ? "Currency conversion"
            : t.is_investment
              ? t.type === "add"
                ? "Sold"
                : "Bought"
              : t.is_savings
                ? t.type === "add"
                  ? "Savings payout"
                  : "Moved to savings"
                : t.is_allowance
                  ? "Allowance"
                  : t.type === "add"
                    ? "Added"
                    : "Deducted";
          return (
            <div
              key={t.id}
              className="bg-card rounded-2xl px-4 py-3 border border-border-hairline flex items-center justify-between"
            >
              <div>
                <div
                  className={`font-semibold text-[14px] capitalize ${t.is_adjustment ? "text-muted" : "text-emerald-dark"}`}
                >
                  {label}
                </div>
                {t.note && <div className="text-[12px] text-muted mt-0.5">{t.note}</div>}
                <div className="text-[11px] text-muted mt-0.5">
                  {formatMoney(t.balance_before, t.previous_currency)} →{" "}
                  {formatMoney(t.balance_after, t.currency)}
                </div>
                <div className="text-[11px] text-muted mt-0.5">{formatDateTime(t.created_at)}</div>
              </div>
              {t.is_adjustment ? (
                // Not a real add/deduct — the balance was just recalculated
                // in the new currency — so no +/- sign and no green/red.
                <div className="font-semibold text-[15px] text-muted">{formatMoney(t.amount, t.currency)}</div>
              ) : (
                <div className={`font-semibold text-[15px] ${t.type === "add" ? "text-positive" : "text-negative"}`}>
                  {t.type === "add" ? "+" : "−"}
                  {formatMoney(t.amount, t.currency)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
