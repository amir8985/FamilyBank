import { notFound } from "next/navigation";
import { requireSession } from "@/lib/session";
import { api, ApiError } from "@/lib/api";
import { BuyFormClient } from "@/components/buy-form-client";
import type { AssetDetailOut, PortfolioOut } from "@/lib/types";

export default async function BuyPage({
  params,
}: {
  params: Promise<{ kidId: string; symbol: string }>;
}) {
  const { kidId, symbol } = await params;
  const session = await requireSession();

  let asset: AssetDetailOut;
  let portfolio: PortfolioOut;
  try {
    [asset, portfolio] = await Promise.all([
      api.get<AssetDetailOut>(`/catalog/${symbol}`, session.backendToken),
      api.get<PortfolioOut>(`/kids/${kidId}/portfolio`, session.backendToken),
    ]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <BuyFormClient
      kidId={kidId}
      kidName={portfolio.kid_name}
      asset={asset}
      currency={session.baseCurrency}
      cashAvailable={Number(portfolio.cash_available)}
    />
  );
}
