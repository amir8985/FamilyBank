import { notFound } from "next/navigation";
import { requireSession } from "@/lib/session";
import { api, ApiError } from "@/lib/api";
import { LotDetailClient } from "@/components/lot-detail-client";
import type { LotDetailOut, PortfolioOut } from "@/lib/types";

export default async function LotDetailPage({
  params,
}: {
  params: Promise<{ kidId: string; lotId: string }>;
}) {
  const { kidId, lotId } = await params;
  const session = await requireSession();

  let lot: LotDetailOut;
  let portfolio: PortfolioOut;
  try {
    [lot, portfolio] = await Promise.all([
      api.get<LotDetailOut>(`/kids/${kidId}/lots/${lotId}`, session.backendToken),
      api.get<PortfolioOut>(`/kids/${kidId}/portfolio`, session.backendToken),
    ]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return <LotDetailClient kidId={kidId} lot={lot} cashAvailable={Number(portfolio.cash_available)} />;
}
