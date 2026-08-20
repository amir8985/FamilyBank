import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { PortfolioClient } from "@/components/portfolio-client";
import type { AssetOut, PortfolioOut } from "@/lib/types";

export default async function KidPortfolioPage({
  params,
}: {
  params: Promise<{ kidId: string }>;
}) {
  const { kidId } = await params;
  const session = await requireSession();

  const [portfolio, catalog] = await Promise.all([
    api.get<PortfolioOut>(`/kids/${kidId}/portfolio`, session.backendToken),
    api.get<AssetOut[]>("/catalog", session.backendToken),
  ]);

  return (
    <PortfolioClient
      kidId={kidId}
      portfolio={portfolio}
      catalog={catalog}
      currency={session.baseCurrency}
    />
  );
}
