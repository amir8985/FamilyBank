"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useFamily } from "@/lib/family-store";
import { invalidateResource } from "@/lib/use-cached-resource";
import { PageHeader } from "@/components/ui/page-header";
import { Money } from "@/components/ui/money";
import { LotChart } from "@/components/ui/lot-chart";
import { TickerBadge } from "@/components/ui/ticker-badge";
import { BoostedBadge, BoostedExplanation } from "@/components/ui/boosted-badge";
import { SellControls } from "@/components/sell-controls";
import { formatMoney, formatPct, formatDateTime, trimUnits } from "@/lib/format";
import type { HoldingOut, LotDetailOut } from "@/lib/types";

export function LotDetailClient({
  kidId,
  lot,
  cashAvailable,
}: {
  kidId: string;
  lot: LotDetailOut;
  cashAvailable: number;
}) {
  const router = useRouter();
  const { refreshHome } = useFamily();
  const [badgeOpen, setBadgeOpen] = useState(false);

  // `current_value`/`purchase_price` are per-unit, in the lot's own
  // native currency (see routes_investing.py's get_lot_detail — this
  // page deliberately shows everything in that native currency rather
  // than converting to the family's, the same way the buy screen's
  // sparkline does for a symbol's raw price history).
  //
  // A fully-sold lot's `units` drops to 0 (see investing_service._sell_lot)
  // — there's no original unit count left to multiply by, so a closed
  // lot shows its per-unit sale price instead of a total.
  const totalValue = Number(lot.current_value) * Number(lot.units);
  const pct = formatPct(lot.since_purchase_pct);
  const positive = Number(lot.since_purchase_pct ?? 0) >= 0;

  const holding: HoldingOut = {
    symbol: lot.symbol,
    display_name: lot.display_name,
    units: lot.units,
    current_value: String(totalValue),
    day_change_pct: null,
    since_purchase_pct: lot.since_purchase_pct,
    lot_id: lot.lot_id,
    is_boosted: Boolean(lot.buffer_rate),
  };

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title={lot.display_name} backHref={`/home/kids/${kidId}`} />

      <div className="px-5 pt-3.5 flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <TickerBadge symbol={lot.symbol} />
          <div>
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="font-semibold text-[15px] text-emerald-dark">{lot.display_name}</span>
              {lot.buffer_rate && (
                <BoostedBadge rate={lot.buffer_rate} onToggle={() => setBadgeOpen((v) => !v)} />
              )}
            </div>
            <div className="text-[12.5px] text-muted">
              {lot.is_open
                ? `${trimUnits(lot.units)} units · bought ${formatDateTime(lot.purchased_at)}`
                : `Bought ${formatDateTime(lot.purchased_at)}`}
            </div>
          </div>
        </div>

        {badgeOpen && lot.buffer_rate && <BoostedExplanation rate={lot.buffer_rate} />}

        {lot.description && (
          <p className="text-[13px] leading-relaxed text-muted-strong">{lot.description}</p>
        )}

        <div className="text-center py-[18px] bg-card border border-border-hairline rounded-2xl">
          <div className="font-serif font-semibold text-[32px] text-emerald">
            {lot.is_open ? (
              <Money amount={totalValue} currency={lot.purchase_currency} />
            ) : (
              <>
                <Money amount={lot.current_value} currency={lot.purchase_currency} />
                <span className="text-[15px] font-sans font-normal text-muted"> / unit</span>
              </>
            )}
          </div>
          {pct && (
            <div className={`text-[13.5px] font-semibold mt-1 ${positive ? "text-positive" : "text-negative"}`}>
              {pct} since bought
            </div>
          )}
        </div>

        <LotChart series={lot.series} currency={lot.purchase_currency} />

        <div className="flex justify-between text-[13.5px] text-muted px-0.5">
          <span>Bought at</span>
          <span className="font-semibold text-emerald-dark">
            {formatMoney(lot.purchase_price, lot.purchase_currency)} / unit
          </span>
        </div>

        {!lot.is_open && (
          <div className="text-center text-[12.5px] text-muted bg-cream rounded-2xl py-3">
            Sold {lot.sold_at ? formatDateTime(lot.sold_at) : ""} — this is its final history.
          </div>
        )}

        {lot.is_open && (
          <SellControls
            kidId={kidId}
            holding={holding}
            cashAvailable={cashAvailable}
            currency={lot.purchase_currency}
            // Any sell here — partial or full — is the natural end of a
            // visit to this page; return to My Investments rather than
            // leaving the parent stranded on a (now stale) lot page.
            onSold={() => {
              invalidateResource(`lot:${kidId}:`);
              invalidateResource(`portfolio:${kidId}`);
              invalidateResource(`debt:${kidId}`);
              invalidateResource(`investment-transactions:${kidId}`);
              refreshHome();
              router.push(`/home/kids/${kidId}`);
            }}
          />
        )}
      </div>
    </div>
  );
}
