"use client";

import { use } from "react";
import { notFound } from "next/navigation";
import { useSession } from "next-auth/react";
import { useCachedResource } from "@/lib/use-cached-resource";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { SavingsKindForm } from "@/components/savings-kind-form";
import type { SavingsPlanOut, SavingsPresetOut } from "@/lib/types";

export default function SavingsKindSettingsPage({
  params,
}: {
  params: Promise<{ kind: string }>;
}) {
  const { kind } = use(params);
  if (kind !== "flexible" && kind !== "locked") notFound();

  const { data: session } = useSession();
  const token = session?.backendToken ?? null;

  const plansRes = useCachedResource<SavingsPlanOut[]>(
    token ? "savings-plans" : null,
    () => api.get<SavingsPlanOut[]>("/family/savings-plans", token as string),
    { ttlMs: 60_000 }
  );
  const presetsRes = useCachedResource<SavingsPresetOut[]>(
    token ? "savings-presets" : null,
    () => api.get<SavingsPresetOut[]>("/family/savings-presets", token as string),
    { ttlMs: 60 * 60_000 }
  );

  if (plansRes.error && !plansRes.data) throw plansRes.error;
  if (presetsRes.error && !presetsRes.data) throw presetsRes.error;

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader
        title={kind === "flexible" ? "Flexible savings" : "Locked savings"}
        backHref="/home/settings/investing"
      />
      {plansRes.data && presetsRes.data ? (
        <SavingsKindForm
          kind={kind}
          plans={plansRes.data}
          presets={presetsRes.data}
          mutatePlans={plansRes.mutate}
          revalidatePlans={plansRes.revalidate}
        />
      ) : (
        <div className="flex flex-col gap-3 px-5 pt-6">
          <Skeleton className="h-14 rounded-2xl" />
          <Skeleton className="h-20 rounded-2xl" />
          <Skeleton className="h-20 rounded-2xl" />
          <Skeleton className="h-44 rounded-2xl" />
        </div>
      )}
    </div>
  );
}
