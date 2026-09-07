"use client";

import { notFound } from "next/navigation";
import { useSession } from "next-auth/react";
import { useFamily } from "@/lib/family-store";
import { useCachedResource } from "@/lib/use-cached-resource";
import { api, ApiError } from "@/lib/api";
import { BuyFormClient } from "@/components/buy-form-client";
import { BuySkeleton } from "@/components/skeletons";
import type { AssetDetailOut, PortfolioOut } from "@/lib/types";

const ASSET_TTL_MS = 10 * 60_000;
const PORTFOLIO_TTL_MS = 15_000;

export function BuyScreen({
  kidId,
  symbol,
  backTab,
}: {
  kidId: string;
  symbol: string;
  backTab: "holdings" | "buy";
}) {
  const { data: session } = useSession();
  const { home } = useFamily();
  const token = session?.backendToken ?? null;
  const summary = home.kids.find((k) => k.id === kidId);

  const assetRes = useCachedResource<AssetDetailOut>(
    token ? `asset:${symbol}` : null,
    () => api.get<AssetDetailOut>(`/catalog/${symbol}`, token as string),
    { ttlMs: ASSET_TTL_MS }
  );
  const portfolioRes = useCachedResource<PortfolioOut>(
    token ? `portfolio:${kidId}` : null,
    () => api.get<PortfolioOut>(`/kids/${kidId}/portfolio`, token as string),
    { ttlMs: PORTFOLIO_TTL_MS }
  );

  if (assetRes.error instanceof ApiError && assetRes.error.status === 404) notFound();
  if (assetRes.error && !assetRes.data) throw assetRes.error;

  // The buy form is only meaningful with the asset's price/step info.
  if (!assetRes.data) return <BuySkeleton />;

  const portfolio = portfolioRes.data;
  const cashAvailable = portfolio
    ? Number(portfolio.cash_available)
    : summary
      ? Number(summary.cash_balance)
      : 0;
  const kidName = portfolio?.kid_name ?? summary?.name ?? "";
  const existingHolding = portfolio?.holdings.find((h) => h.symbol === symbol) ?? null;

  return (
    <BuyFormClient
      key={assetRes.data.symbol}
      kidId={kidId}
      kidName={kidName}
      asset={assetRes.data}
      currency={home.base_currency}
      cashAvailable={cashAvailable}
      backHref={`/home/kids/${kidId}?tab=${backTab}`}
      existingHolding={existingHolding}
    />
  );
}
