"use client";

import { useSession } from "next-auth/react";
import { useFamily } from "@/lib/family-store";
import { useCachedResource } from "@/lib/use-cached-resource";
import { api } from "@/lib/api";
import { PortfolioClient } from "@/components/portfolio-client";
import type { AssetOut, KidSummary, PortfolioOut } from "@/lib/types";

const CATALOG_TTL_MS = 10 * 60_000; // scheduler refreshes prices every ~5h
const PORTFOLIO_TTL_MS = 15_000;

/** Builds a stand-in portfolio from the `/home` kid summary so the header
 * (name, cash, invested total, day change) renders instantly on
 * navigation from Home. Holdings fill in when the real fetch resolves. */
function synthesizePortfolio(kidId: string, summary: KidSummary | undefined): PortfolioOut {
  const cash = summary ? Number(summary.cash_balance) : 0;
  const invested = summary ? Number(summary.portfolio_value) : 0;
  return {
    kid_id: kidId,
    kid_name: summary?.name ?? "",
    cash_available: String(cash),
    holdings_value: String(invested),
    total_value: String(cash + invested),
    total_day_change_amount: "0",
    total_day_change_pct: summary?.portfolio_day_change_pct ?? null,
    holdings: [],
    prices_as_of: null,
  };
}

export function KidPortfolioScreen({
  kidId,
  initialTab,
}: {
  kidId: string;
  initialTab: "holdings" | "buy";
}) {
  const { data: session } = useSession();
  const { home } = useFamily();
  const token = session?.backendToken ?? null;
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

  // Deleted kid / bad link: nothing to show and the fetch has failed —
  // let the segment error boundary handle it, matching prior behavior.
  if (portfolioRes.error && !portfolioRes.data && !summary) {
    throw portfolioRes.error;
  }

  const portfolio = portfolioRes.data ?? synthesizePortfolio(kidId, summary);

  return (
    <PortfolioClient
      kidId={kidId}
      portfolio={portfolio}
      catalog={catalogRes.data ?? []}
      currency={home.base_currency}
      initialTab={initialTab}
      holdingsLoading={!portfolioRes.data}
      catalogLoading={!catalogRes.data}
    />
  );
}
