"use client";

import { useState } from "react";
import Link from "next/link";
import { TickerBadge } from "@/components/ui/ticker-badge";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { SellSheet } from "@/components/sell-sheet";
import { formatMoney, formatPct, formatSignedMoney, formatUnits } from "@/lib/format";
import type { AssetOut, HoldingOut, PortfolioOut } from "@/lib/types";

export function PortfolioClient({
  kidId,
  portfolio,
  catalog,
  currency,
}: {
  kidId: string;
  portfolio: PortfolioOut;
  catalog: AssetOut[];
  currency: string;
}) {
  const [tab, setTab] = useState<"holdings" | "buy">("holdings");
  const [sellTarget, setSellTarget] = useState<HoldingOut | null>(null);

  const dayChangePct = formatPct(portfolio.total_day_change_pct);
  const isPositive = Number(portfolio.total_day_change_amount) >= 0;

  return (
    <div className="max-w-md mx-auto flex flex-col min-h-screen">
      <div className="pt-[58px] px-5 pb-1 flex items-center gap-2.5">
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

      <div className="px-5 pt-3.5 pb-1">
        <div className="text-[13px] font-medium text-muted">Total value</div>
        <div className="font-serif font-semibold text-[32px] text-emerald">
          {formatMoney(portfolio.total_value, currency)}
        </div>
        {dayChangePct && (
          <div className={`text-[13px] font-semibold ${isPositive ? "text-positive" : "text-negative"}`}>
            {formatSignedMoney(portfolio.total_day_change_amount, currency)} today ({dayChangePct.replace("+", "")})
          </div>
        )}
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
              const pct = formatPct(h.day_change_pct);
              const positive = Number(h.day_change_pct ?? 0) >= 0;
              return (
                <button
                  key={h.symbol}
                  type="button"
                  onClick={() => setSellTarget(h)}
                  className="text-left bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex items-center justify-between cursor-pointer"
                >
                  <div className="flex items-center gap-3">
                    <TickerBadge symbol={h.symbol} />
                    <div>
                      <div className="font-semibold text-[15px] text-emerald-dark">{h.display_name}</div>
                      <div className="text-[12.5px] text-muted">{formatUnits(h.units)} units</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold text-[15px] text-emerald-dark">
                      {formatMoney(h.current_value, currency)}
                    </div>
                    {pct && (
                      <div className={`font-semibold text-[12.5px] ${positive ? "text-positive" : "text-negative"}`}>
                        {pct}
                      </div>
                    )}
                  </div>
                </button>
              );
            })}

            <div className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex items-center justify-between">
              <div className="text-[14px] font-medium text-muted">Cash available</div>
              <div className="font-bold text-[16px] text-emerald">
                {formatMoney(portfolio.cash_available, currency)}
              </div>
            </div>

            {portfolio.holdings.length === 0 && (
              <p className="text-center text-[13px] text-muted pt-4">
                No investments yet — switch to Buy to get started.
              </p>
            )}
          </>
        ) : (
          catalog.map((asset) => {
            const pct = formatPct(asset.day_change_pct);
            const positive = Number(asset.day_change_pct ?? 0) >= 0;
            return (
              <Link
                key={asset.symbol}
                href={`/home/kids/${kidId}/buy/${asset.symbol}`}
                className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <TickerBadge symbol={asset.symbol} />
                  <div>
                    <div className="font-semibold text-[15px] text-emerald-dark">{asset.display_name}</div>
                    <div className="text-[12.5px] text-muted capitalize">{asset.kind}</div>
                  </div>
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
          })
        )}
      </div>

      {sellTarget && (
        <SellSheet
          onClose={() => setSellTarget(null)}
          kidId={kidId}
          holding={sellTarget}
          cashAvailable={Number(portfolio.cash_available)}
          currency={currency}
        />
      )}
    </div>
  );
}
