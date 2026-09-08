import Link from "next/link";
import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { HubStillGrowingBadge } from "@/components/ui/hub-still-growing";
import type { FamilySettings, SavingsPlanOut } from "@/lib/types";

// A hub for special per-kid investing/savings features — each is a
// teaser card leading to its own settings screen (see CLAUDE.md's
// boosted-stocks-and-interest / savings-plans status entries).
export default async function InvestingSettingsPage() {
  const session = await requireSession();
  const [settings, plans] = await Promise.all([
    api.get<FamilySettings>("/family/settings", session.backendToken),
    api.get<SavingsPlanOut[]>("/family/savings-plans", session.backendToken),
  ]);
  const boostActive = settings.boost_buffer_rate !== null;

  const growingCount = (isLocked: (m: number) => boolean) =>
    plans
      .filter((p) => !p.is_active && isLocked(p.lock_months))
      .reduce((n, p) => n + p.open_deposit_count, 0);

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title="Advanced investing & savings" backHref="/home/settings" />

      <div className="flex flex-col gap-3 px-5 pt-4 pb-8">
        <Card
          title="Stock boost"
          active={boostActive}
          growingCount={0}
          kind="flexible"
          blurb="Real stock moves can feel painfully slow for kids on small amounts. A boost gives your kid's gains a little extra kick — so investing feels worth their while."
          href="/home/settings/investing/boost"
          cta="Stock boost settings"
        />
        <Card
          title="Flexible savings"
          active={plans.some((p) => p.is_active && p.lock_months === 0)}
          growingCount={growingCount((m) => m === 0)}
          kind="flexible"
          blurb="A place for your kid to set money aside and earn interest on it — with no strings, so they can take it back out whenever they want."
          href="/home/settings/investing/savings/flexible"
          cta="Flexible savings settings"
        />
        <Card
          title="Locked savings"
          active={plans.some((p) => p.is_active && p.lock_months > 0)}
          growingCount={growingCount((m) => m > 0)}
          kind="locked"
          blurb="Higher interest in exchange for leaving the money untouched for a set stretch — a month, a few months, up to a year."
          href="/home/settings/investing/savings/locked"
          cta="Locked savings settings"
        />
      </div>
    </div>
  );
}

function Card({
  title,
  active,
  growingCount,
  kind,
  blurb,
  href,
  cta,
}: {
  title: string;
  active: boolean;
  growingCount: number;
  kind: "flexible" | "locked";
  blurb: string;
  href: string;
  cta: string;
}) {
  return (
    <div className="flex flex-col gap-2.5 bg-card rounded-2xl px-4 py-4 border border-border-hairline">
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-1.5">
          <h2 className="font-serif font-semibold text-[16px] text-emerald-dark">{title}</h2>
          {active && (
            <span className="text-[10px] font-semibold text-tint-dark bg-tint-emerald rounded-full px-1.5 py-0.5">
              Active
            </span>
          )}
        </div>
        {!active && growingCount > 0 && <HubStillGrowingBadge count={growingCount} kind={kind} />}
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
