"use client";

import { use } from "react";
import { notFound } from "next/navigation";
import { useFamily } from "@/lib/family-store";
import { useCachedResource } from "@/lib/use-cached-resource";
import { api, ApiError } from "@/lib/api";
import { SavingsDepositClient } from "@/components/savings-deposit-client";
import { BuySkeleton } from "@/components/skeletons";
import type { SavingsDepositDetailOut } from "@/lib/types";

export default function SavingsDepositPage({
  params,
}: {
  params: Promise<{ kidId: string; depositId: string }>;
}) {
  const { kidId, depositId } = use(params);
  const { token } = useFamily();

  const res = useCachedResource<SavingsDepositDetailOut>(
    token ? `savings-deposit:${kidId}:${depositId}` : null,
    () => api.get<SavingsDepositDetailOut>(`/kids/${kidId}/savings/${depositId}`, token as string),
    { ttlMs: 15_000 }
  );

  if (res.error instanceof ApiError && res.error.status === 404) notFound();
  if (res.error && !res.data) throw res.error;
  if (!res.data) return <BuySkeleton />;

  return <SavingsDepositClient kidId={kidId} deposit={res.data} />;
}
