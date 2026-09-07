"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import { useCachedResource } from "@/lib/use-cached-resource";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import type { FamilySettings } from "@/lib/types";

// A hub for special per-kid investing/savings features — right now just
// stock boost, but built as a list of teaser cards each leading to its
// own settings screen so a future "interest" feature slots in the same
// way (see CLAUDE.md's boosted-stocks-and-interest status entry).
export default function InvestingSettingsPage() {
  const { data: session } = useSession();
  const token = session?.backendToken ?? null;
  const { data: settings } = useCachedResource<FamilySettings>(
    token ? "family-settings" : null,
    () => api.get<FamilySettings>("/family/settings", token as string),
    { ttlMs: 5 * 60_000 }
  );
  const boostActive = settings ? settings.boost_buffer_rate !== null : null;

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title="Advanced investing & savings" backHref="/home/settings" />

      <div className="flex flex-col gap-3 px-5 pt-4 pb-8">
        <div className="flex flex-col gap-2.5 bg-card rounded-2xl px-4 py-4 border border-border-hairline">
          <div className="flex items-center gap-1.5">
            <h2 className="font-serif font-semibold text-[16px] text-emerald-dark">Stock boost</h2>
            {boostActive === null ? (
              <Skeleton className="h-4 w-12" />
            ) : (
              boostActive && (
                <span className="text-[10px] font-semibold text-tint-dark bg-tint-emerald rounded-full px-1.5 py-0.5">
                  Active
                </span>
              )
            )}
          </div>
          <p className="text-[13.5px] text-muted leading-relaxed">
            Real stock moves can feel painfully slow for kids on small amounts. A boost gives your
            kid&apos;s gains a little extra kick — so investing feels worth their while.
          </p>
          <Link
            href="/home/settings/investing/boost"
            className="bg-emerald text-white text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold"
          >
            Stock boost settings
          </Link>
        </div>
      </div>
    </div>
  );
}
