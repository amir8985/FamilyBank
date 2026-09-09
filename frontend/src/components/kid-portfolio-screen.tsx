"use client";

import { useFamily } from "@/lib/family-store";
import { useCachedResource } from "@/lib/use-cached-resource";
import { api } from "@/lib/api";
import { PortfolioClient } from "@/components/portfolio-client";
import type { AssetOut, KidSummary, PortfolioOut, SavingsOverviewOut } from "@/lib/types";

const CATALOG_TTL_MS = 10 * 60_000; // scheduler refreshes prices every ~5h
const PORTFOLIO_TTL_MS = 15_000;
const SAVINGS_TTL_MS = 15_000;

/** Builds a stand-in portfolio from the `/home` kid summary so the header
 * (name, cash, invested total) renders instantly on navigation from Home.
 * Holdings and the day-change figure fill in when the real fetch resolves
 * — the summary carries a day-change %, but not the signed amount that
 * drives its colour, so it's left out of the placeholder rather than
 * shown in the wrong colour for a beat. */
function synthesizePortfolio(kidId: string, summary: KidSummary | undefined): PortfolioOut {
  const cash = summary ? Number(summary.cash_balance) : 0;
  const invested = summary ? Number(summary.portfolio_value) : 0;
  return {
    kid_id: kidId,
    kid_name: summary?.name ?? "",
    cash_available: String(cash),
    holdings_value: String(invested),
    savings_value: "0",
    total_value: String(cash + invested),
    total_day_change_amount: "0",
    total_day_change_pct: null,
    holdings: [],
    prices_as_of: null,
    boost_buffer_rate: null,
  };
}

const EMPTY_SAVINGS: SavingsOverviewOut = { savings_value: "0", deposits: [], plans: [] };

export function KidPortfolioScreen({
  kidId,
  initialTab,
}: {
  kidId: string;
  initialTab: "holdings" | "buy" | "save";
}) {
  const { home, token } = useFamily();
  const summary = home.kids.find((k) => k.id === kidId);

  const portfolioRes = useCachedResource<PortfolioOut>(
    token ? `portfolio:${kidId}` : null,
    () => api.get<PortfolioOut>(`/kids/${kidId}/portfolio`, token as string),
    { ttlMs: PORTFOLIO_TTL_MS }
  );
  const catalogRes = useCachedResource<AssetOut[]>(
    token ? "catalog" : null,
    () => api.get<AssetOut[]>("/catalog", token as string),
    { ttlMs: CATALOG_TTL_MS }
  );
  const savingsRes = useCachedResource<SavingsOverviewOut>(
    token ? `savings:${kidId}` : null,
    () => api.get<SavingsOverviewOut>(`/kids/${kidId}/savings`, token as string),
    { ttlMs: SAVINGS_TTL_MS }
  );

  // Portfolio fetch failed and we have nothing cached — route to the
  // segment error boundary (matching the pre-instant-UX behavior of a
  // thrown ApiError). The summary-only placeholder is for the loading
  // window, not for a hard failure.
  if (portfolioRes.error && !portfolioRes.data) {
    throw portfolioRes.error;
  }

  const portfolio = portfolioRes.data ?? synthesizePortfolio(kidId, summary);

  return (
    <PortfolioClient
      kidId={kidId}
      portfolio={portfolio}
      savings={savingsRes.data ?? EMPTY_SAVINGS}
      catalog={catalogRes.data ?? []}
      currency={home.base_currency}
      initialTab={initialTab}
      holdingsLoading={!portfolioRes.data}
      catalogLoading={!catalogRes.data}
      savingsLoading={!savingsRes.data}
    />
  );
}
