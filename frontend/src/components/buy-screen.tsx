"use client";

import { notFound } from "next/navigation";
import { useSession } from "next-auth/react";
import { useFamily } from "@/lib/family-store";
import { useCachedResource } from "@/lib/use-cached-resource";
import { api, ApiError } from "@/lib/api";
import { BuyFormClient } from "@/components/buy-form-client";
import { BuySkeleton } from "@/components/skeletons";
import type { AssetDetailOut, FamilySettings, PortfolioOut } from "@/lib/types";

const ASSET_TTL_MS = 10 * 60_000;
const PORTFOLIO_TTL_MS = 15_000;
const SETTINGS_TTL_MS = 5 * 60_000;

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
  const settingsRes = useCachedResource<FamilySettings>(
    token ? "family-settings" : null,
    () => api.get<FamilySettings>("/family/settings", token as string),
    { ttlMs: SETTINGS_TTL_MS }
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

  // A symbol can match more than one holding — buy() never merges
  // separate purchases (boost lots). Used for the "you already own N
  // units" line. The one holding this screen can still sell inline is a
  // pre-lot legacy avg-cost holding (no lot_id) reached from My
  // Investments — every lot-based one has its own /lots/[lotId] page.
  const matchingHoldings = (portfolio?.holdings ?? []).filter((h) => h.symbol === symbol);
  const sellableHolding =
    backTab === "holdings" ? (matchingHoldings.find((h) => !h.lot_id) ?? null) : null;

  return (
    <BuyFormClient
      key={assetRes.data.symbol}
      kidId={kidId}
      kidName={kidName}
      asset={assetRes.data}
      currency={home.base_currency}
      cashAvailable={cashAvailable}
      backHref={`/home/kids/${kidId}?tab=${backTab}`}
      matchingHoldings={matchingHoldings}
      sellableHolding={sellableHolding}
      boostBufferRate={settingsRes.data?.boost_buffer_rate ?? null}
    />
  );
}
