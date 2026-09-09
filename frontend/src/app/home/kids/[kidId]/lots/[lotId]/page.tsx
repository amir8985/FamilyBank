"use client";

import { use } from "react";
import { notFound } from "next/navigation";
import { useFamily } from "@/lib/family-store";
import { useCachedResource } from "@/lib/use-cached-resource";
import { api, ApiError } from "@/lib/api";
import { LotDetailClient } from "@/components/lot-detail-client";
import { BuySkeleton } from "@/components/skeletons";
import type { LotDetailOut, PortfolioOut } from "@/lib/types";

export default function LotDetailPage({
  params,
}: {
  params: Promise<{ kidId: string; lotId: string }>;
}) {
  const { kidId, lotId } = use(params);
  const { home, token } = useFamily();
  const summary = home.kids.find((k) => k.id === kidId);

  const lotRes = useCachedResource<LotDetailOut>(
    token ? `lot:${kidId}:${lotId}` : null,
    () => api.get<LotDetailOut>(`/kids/${kidId}/lots/${lotId}`, token as string),
    { ttlMs: 15_000 }
  );
  const portfolioRes = useCachedResource<PortfolioOut>(
    token ? `portfolio:${kidId}` : null,
    () => api.get<PortfolioOut>(`/kids/${kidId}/portfolio`, token as string),
    { ttlMs: 15_000 }
  );

  if (lotRes.error instanceof ApiError && lotRes.error.status === 404) notFound();
  if (lotRes.error && !lotRes.data) throw lotRes.error;

  if (!lotRes.data) return <BuySkeleton />;

  const cashAvailable = portfolioRes.data
    ? Number(portfolioRes.data.cash_available)
    : summary
      ? Number(summary.cash_balance)
      : 0;

  return <LotDetailClient kidId={kidId} lot={lotRes.data} cashAvailable={cashAvailable} />;
}
