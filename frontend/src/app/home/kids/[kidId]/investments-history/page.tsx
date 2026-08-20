import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { TickerBadge } from "@/components/ui/ticker-badge";
import { formatDateTime, formatMoney, trimUnits } from "@/lib/format";
import type { InvestmentTransactionOut, PortfolioOut } from "@/lib/types";

export default async function KidInvestmentHistoryPage({
  params,
}: {
  params: Promise<{ kidId: string }>;
}) {
  const { kidId } = await params;
  const session = await requireSession();

  const [transactions, portfolio] = await Promise.all([
    api.get<InvestmentTransactionOut[]>(`/kids/${kidId}/investment-transactions`, session.backendToken),
    api.get<PortfolioOut>(`/kids/${kidId}/portfolio`, session.backendToken),
  ]);

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title={`${portfolio.kid_name}'s Investment History`} backHref={`/home/kids/${kidId}`} />

      <div className="flex-1 px-5 pt-3 pb-6 flex flex-col gap-2.5">
        {transactions.length === 0 && (
          <p className="text-center text-[13px] text-muted pt-4">No buys or sells yet.</p>
        )}
        {transactions.map((t) => {
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
