"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import { useCachedResource } from "@/lib/use-cached-resource";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { HubDeactivatedBadge, HubStillGrowingBadge } from "@/components/ui/hub-savings-badges";
import type { FamilySettings, SavingsPlanOut } from "@/lib/types";

// A hub for special per-kid investing/savings features — each is a
// teaser card leading to its own settings screen (see CLAUDE.md's
// boosted-stocks-and-interest / savings-plans status entries).
export default function InvestingSettingsPage() {
  const { data: session } = useSession();
  const token = session?.backendToken ?? null;

  const { data: settings } = useCachedResource<FamilySettings>(
    token ? "family-settings" : null,
    () => api.get<FamilySettings>("/family/settings", token as string),
    { ttlMs: 5 * 60_000 }
  );
  const { data: plans } = useCachedResource<SavingsPlanOut[]>(
    token ? "savings-plans" : null,
    () => api.get<SavingsPlanOut[]>("/family/savings-plans", token as string),
    { ttlMs: 60_000 }
  );

  const boostActive = settings ? settings.boost_buffer_rate !== null : null;

  const kindState = (isKind: (m: number) => boolean) => {
    if (!plans) return null;
    const kindPlans = plans.filter((p) => isKind(p.lock_months));
    return {
      active: kindPlans.some((p) => p.is_active),
      growingCount: kindPlans
        .filter((p) => !p.is_active)
        .reduce((n, p) => n + p.open_deposit_count, 0),
    };
  };

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

        <SavingsCard
          title="Flexible savings"
          kind="flexible"
          state={kindState((m) => m === 0)}
          blurb="A place for your kid to set money aside and earn interest on it — with no strings, so they can take it back out whenever they want."
          href="/home/settings/investing/savings/flexible"
          cta="Flexible savings settings"
        />
        <SavingsCard
          title="Locked savings"
          kind="locked"
          state={kindState((m) => m > 0)}
          blurb="Higher interest in exchange for leaving the money untouched for a set stretch — a month, a few months, up to a year."
          href="/home/settings/investing/savings/locked"
          cta="Locked savings settings"
        />
      </div>
    </div>
  );
}

function SavingsCard({
  title,
  kind,
  state,
  blurb,
  href,
  cta,
}: {
  title: string;
  kind: "flexible" | "locked";
  state: { active: boolean; growingCount: number } | null;
  blurb: string;
  href: string;
  cta: string;
}) {
  return (
    <div className="flex flex-col gap-2.5 bg-card rounded-2xl px-4 py-4 border border-border-hairline">
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-1.5 flex-wrap">
          <h2 className="font-serif font-semibold text-[16px] text-emerald-dark">{title}</h2>
          {state === null ? (
            <Skeleton className="h-4 w-12" />
          ) : (
            state.active && (
              <span className="text-[10px] font-semibold text-tint-dark bg-tint-emerald rounded-full px-1.5 py-0.5">
                Active
              </span>
            )
          )}
        </div>
        {state && !state.active && <HubDeactivatedBadge kind={kind} />}
        {state && !state.active && state.growingCount > 0 && (
          <HubStillGrowingBadge count={state.growingCount} kind={kind} />
        )}
      </div>
      <p className="text-[13.5px] text-muted leading-relaxed">{blurb}</p>
      <Link
        href={href}
        className="bg-emerald text-white text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold"
      >
        {cta}
      </Link>
    </div>
  );
}
