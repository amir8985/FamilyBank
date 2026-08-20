import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { PortfolioClient } from "@/components/portfolio-client";
import type { AssetOut, FamilySettings, PortfolioOut } from "@/lib/types";

export default async function KidPortfolioPage({
  params,
  searchParams,
}: {
  params: Promise<{ kidId: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const { kidId } = await params;
  const { tab } = await searchParams;
  const session = await requireSession();

  // Fetched fresh on every load rather than trusting session.baseCurrency
  // — that value is only as fresh as the last sign-in, so it goes stale
  // the moment someone changes currency in Settings.
  const [portfolio, catalog, settings] = await Promise.all([
    api.get<PortfolioOut>(`/kids/${kidId}/portfolio`, session.backendToken),
    api.get<AssetOut[]>("/catalog", session.backendToken),
    api.get<FamilySettings>("/family/settings", session.backendToken),
  ]);

  return (
    <PortfolioClient
      kidId={kidId}
      portfolio={portfolio}
      catalog={catalog}
      currency={settings.base_currency}
      initialTab={tab === "buy" ? "buy" : "holdings"}
    />
  );
}
