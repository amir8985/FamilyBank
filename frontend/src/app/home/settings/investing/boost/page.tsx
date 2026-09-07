"use client";

import { useSession } from "next-auth/react";
import { useCachedResource } from "@/lib/use-cached-resource";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { BoostSettingsForm } from "@/components/boost-settings-form";
import { Skeleton } from "@/components/ui/skeleton";
import type { FamilySettings } from "@/lib/types";

export default function BoostSettingsPage() {
  const { data: session } = useSession();
  const token = session?.backendToken ?? null;
  const { data: settings } = useCachedResource<FamilySettings>(
    token ? "family-settings" : null,
    () => api.get<FamilySettings>("/family/settings", token as string),
    { ttlMs: 5 * 60_000 }
  );

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      {/* Back skips the one-card hub and goes straight to Settings —
          the hub adds nothing to return through, and the user asked for
          a faster way out of this screen specifically. */}
      <PageHeader title="Stock boost" backHref="/home/settings" />
      {settings ? (
        <BoostSettingsForm currentRate={settings.boost_buffer_rate} />
      ) : (
        <div className="flex flex-col gap-4 px-5 pt-4">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-11 w-full" />
        </div>
      )}
    </div>
  );
}
