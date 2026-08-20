import { notFound } from "next/navigation";
import { requireSession } from "@/lib/session";
import { api, ApiError } from "@/lib/api";
import { BuyFormClient } from "@/components/buy-form-client";
import type { AssetDetailOut, FamilySettings, PortfolioOut } from "@/lib/types";

export default async function BuyPage({
  params,
  searchParams,
}: {
  params: Promise<{ kidId: string; symbol: string }>;
  searchParams: Promise<{ from?: string }>;
}) {
  const { kidId, symbol } = await params;
  const { from } = await searchParams;
  const session = await requireSession();

  let asset: AssetDetailOut;
  let portfolio: PortfolioOut;
  let settings: FamilySettings;
  try {
    [asset, portfolio, settings] = await Promise.all([
      api.get<AssetDetailOut>(`/catalog/${symbol}`, session.backendToken),
      api.get<PortfolioOut>(`/kids/${kidId}/portfolio`, session.backendToken),
      // Fetched fresh, not from session.baseCurrency — see kids/[kidId]/page.tsx.
      api.get<FamilySettings>("/family/settings", session.backendToken),
    ]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  // Preserves which tab (My Investments vs Buy) the user came from, so
  // the back chevron returns them there instead of always resetting to
  // the default tab.
  const backTab = from === "buy" ? "buy" : "holdings";
  const existingHolding = portfolio.holdings.find((h) => h.symbol === symbol) ?? null;

  return (
    <BuyFormClient
      key={asset.symbol}
      kidId={kidId}
      kidName={portfolio.kid_name}
      asset={asset}
      currency={settings.base_currency}
      cashAvailable={Number(portfolio.cash_available)}
      backHref={`/home/kids/${kidId}?tab=${backTab}`}
      existingHolding={existingHolding}
    />
  );
}
