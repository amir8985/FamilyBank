import { notFound } from "next/navigation";
import { requireSession } from "@/lib/session";
import { api, ApiError } from "@/lib/api";
import { SavingsDepositClient } from "@/components/savings-deposit-client";
import type { SavingsDepositDetailOut } from "@/lib/types";

export default async function SavingsDepositPage({
  params,
}: {
  params: Promise<{ kidId: string; depositId: string }>;
}) {
  const { kidId, depositId } = await params;
  const session = await requireSession();

  let deposit: SavingsDepositDetailOut;
  try {
    deposit = await api.get<SavingsDepositDetailOut>(
      `/kids/${kidId}/savings/${depositId}`,
      session.backendToken,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return <SavingsDepositClient kidId={kidId} deposit={deposit} />;
}
