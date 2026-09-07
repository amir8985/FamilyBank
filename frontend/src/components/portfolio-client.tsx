"use client";

import { useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { TickerBadge } from "@/components/ui/ticker-badge";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Money } from "@/components/ui/money";
import { api, ApiError } from "@/lib/api";
import { formatMoney, formatPct, trimUnits } from "@/lib/format";
import type { AssetOut, PortfolioOut } from "@/lib/types";

export function PortfolioClient({
  kidId,
  portfolio,
  catalog,
  currency,
  initialTab,
}: {
  kidId: string;
  portfolio: PortfolioOut;
  catalog: AssetOut[];
  currency: string;
  initialTab: "holdings" | "buy";
}) {
  const { data: session } = useSession();
  const router = useRouter();
  const [tab, setTab] = useState<"holdings" | "buy">(initialTab);
  const [sellingAll, setSellingAll] = useState(false);
  const [sellAllError, setSellAllError] = useState<string | null>(null);

  const dayChangePct = formatPct(portfolio.total_day_change_pct);
  const isPositive = Number(portfolio.total_day_change_amount) >= 0;

  async function handleSellEverything() {
    if (!session?.backendToken) return;
    if (!confirm(`Sell everything ${portfolio.kid_name} owns? This can't be undone.`)) return;
    setSellingAll(true);
    setSellAllError(null);
    try {
      await api.post(`/kids/${kidId}/sell-all`, session.backendToken);
      router.refresh();
    } catch (e) {
      setSellAllError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setSellingAll(false);
    }
  }

  return (
    <div className="max-w-md mx-auto flex flex-col min-h-screen">
      <div className="pt-[58px] px-5 pb-1 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Link
            href="/home"
            aria-label="Back"
            className="w-[26px] h-[26px] flex items-center justify-center text-emerald text-lg"
          >
            ‹
          </Link>
          <h1 className="font-serif font-semibold text-[19px] text-emerald-dark">
            {portfolio.kid_name}&apos;s Investments
          </h1>
        </div>
        <Link href={`/home/kids/${kidId}/investments-history`} className="text-[12.5px] font-semibold text-emerald">
          History
        </Link>
      </div>

      <div className="px-5 pt-3.5 pb-1">
        <div className="text-[13px] font-medium text-muted">Cash available</div>
        <div className="font-serif font-semibold text-[32px] text-emerald">
          <Money amount={portfolio.cash_available} currency={currency} />
        </div>
        <div className="flex items-baseline gap-1.5 mt-1">
          <span className="text-[14px] font-medium text-muted-strong">
            {formatMoney(portfolio.holdings_value, currency)} invested
          </span>
          {dayChangePct && (
            <span className={`text-[13px] font-semibold ${isPositive ? "text-positive" : "text-negative"}`}>
              {dayChangePct}
            </span>
          )}
        </div>
      </div>

      <div className="px-5 pt-2 pb-2">
        <SegmentedControl
          value={tab}
          onChange={setTab}
          options={[
            { value: "holdings", label: "My Investments" },
            { value: "buy", label: "Buy" },
          ]}
        />
      </div>

      <div className="flex-1 px-5 pt-2 pb-6 flex flex-col gap-2.5">
        {tab === "holdings" ? (
          <>
            {portfolio.holdings.map((h) => {
              // "Since you bought it" — how the position has actually
              // done — rather than today's daily wiggle, which is what
              // the catalog/Buy tab shows instead.
              const pct = formatPct(h.since_purchase_pct);
              const positive = Number(h.since_purchase_pct ?? 0) >= 0;
              // A lot goes to its own detail page (chart since purchase +
              // sell) — never the Buy screen, which is for buying, not for
              // viewing/selling something already owned. Only a
              // pre-lot legacy avg-cost holding (no lot_id) still uses the
              // Buy page's "you own this" banner, since it has no
              // dedicated detail page of its own.
              const href = h.lot_id
                ? `/home/kids/${kidId}/lots/${h.lot_id}`
                : `/home/kids/${kidId}/buy/${h.symbol}?from=holdings`;
              return (
                <Link
                  key={h.lot_id ?? h.symbol}
                  href={href}
                  className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <TickerBadge symbol={h.symbol} />
                    <div>
                      <div className="font-semibold text-[15px] text-emerald-dark">
                        {h.display_name}
                        {h.is_boosted && (
                          <span className="ml-1.5 align-middle text-[10px] font-semibold text-tint-dark bg-tint-emerald rounded-full px-1.5 py-0.5">
                            Boosted
                          </span>
                        )}
                      </div>
                      <div className="text-[12.5px] text-muted">{trimUnits(h.units)} units</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold text-[15px] text-emerald-dark">
                      {formatMoney(h.current_value, currency)}
                    </div>
                    {pct && (
                      <div className={`font-semibold text-[12.5px] ${positive ? "text-positive" : "text-negative"}`}>
                        {pct} since bought
                      </div>
                    )}
                  </div>
                </Link>
              );
            })}

            {portfolio.holdings.length === 0 && (
              <p className="text-center text-[13px] text-muted pt-4">
                No investments yet — switch to Buy to get started.
              </p>
            )}

            {portfolio.holdings.length > 0 && (
              <>
                <button
                  type="button"
                  disabled={sellingAll}
                  onClick={handleSellEverything}
                  className="mt-1 text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold border border-negative text-negative cursor-pointer disabled:opacity-50"
                >
                  {sellingAll ? "Selling…" : `Sell everything for ${formatMoney(portfolio.holdings_value, currency)}`}
                </button>
                {sellAllError && <p className="text-[13px] text-negative -mt-1">{sellAllError}</p>}
              </>
            )}
          </>
        ) : (
          <>
            <CatalogSection
              title="Baskets"
              subtitle="A slice of many companies at once — steadier, simpler."
              assets={catalog.filter((a) => a.kind === "basket")}
              kidId={kidId}
              currency={currency}
            />
            <CatalogSection
              title="Individual stocks"
              subtitle="One company at a time — more ups and downs."
              assets={catalog.filter((a) => a.kind === "stock")}
              kidId={kidId}
              currency={currency}
            />
          </>
        )}
      </div>
    </div>
  );
}

function CatalogSection({
  title,
  subtitle,
  assets,
  kidId,
  currency,
}: {
  title: string;
  subtitle: string;
  assets: AssetOut[];
  kidId: string;
  currency: string;
}) {
  if (assets.length === 0) return null;
  return (
    <div className="flex flex-col gap-2.5">
      <div className="pt-1">
        <h2 className="font-serif font-semibold text-[16px] text-emerald-dark">{title}</h2>
        <p className="text-[12px] text-muted">{subtitle}</p>
      </div>
      {assets.map((asset) => {
        const pct = formatPct(asset.day_change_pct);
        const positive = Number(asset.day_change_pct ?? 0) >= 0;
        return (
          <Link
            key={asset.symbol}
            href={`/home/kids/${kidId}/buy/${asset.symbol}?from=buy`}
            className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <TickerBadge symbol={asset.symbol} />
              <div className="font-semibold text-[15px] text-emerald-dark">{asset.display_name}</div>
            </div>
            <div className="text-right">
              {asset.price ? (
                <>
                  <div className="font-semibold text-[15px] text-emerald-dark">
                    {formatMoney(asset.price, currency)}
                  </div>
                  {pct && (
                    <div className={`font-semibold text-[12.5px] ${positive ? "text-positive" : "text-negative"}`}>
                      {pct}
                    </div>
                  )}
                </>
              ) : (
                <div className="text-[12.5px] text-muted">price pending</div>
              )}
            </div>
          </Link>
        );
      })}
    </div>
  );
}
