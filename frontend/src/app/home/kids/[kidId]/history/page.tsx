import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { DebtTransactionOut, PortfolioOut } from "@/lib/types";

export default async function KidHistoryPage({
  params,
}: {
  params: Promise<{ kidId: string }>;
}) {
  const { kidId } = await params;
  const session = await requireSession();

  const [transactions, portfolio] = await Promise.all([
    api.get<DebtTransactionOut[]>(`/kids/${kidId}/debt`, session.backendToken),
    api.get<PortfolioOut>(`/kids/${kidId}/portfolio`, session.backendToken),
  ]);

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title={`${portfolio.kid_name}'s History`} backHref="/home" />

      <div className="flex-1 px-5 pt-3 pb-6 flex flex-col gap-2.5">
        {transactions.length === 0 && (
          <p className="text-center text-[13px] text-muted pt-4">No balance changes yet.</p>
        )}
        {transactions.map((t) => {
          const label = t.is_adjustment
            ? "Currency conversion"
            : t.is_investment
              ? t.type === "add"
                ? "Sold"
                : "Bought"
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
                // Not a real add/deduct — nothing was actually given or taken
                // away, the balance was just recalculated in the new
                // currency — so no +/- sign and no green/red framing.
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
