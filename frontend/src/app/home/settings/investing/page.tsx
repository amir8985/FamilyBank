import Link from "next/link";
import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
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
  const activePlanCount = plans.filter((p) => p.is_active).length;

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title="Advanced investing & savings" backHref="/home/settings" />

      <div className="flex flex-col gap-3 px-5 pt-4 pb-8">
        <div className="flex flex-col gap-2.5 bg-card rounded-2xl px-4 py-4 border border-border-hairline">
          <div className="flex items-center gap-1.5">
            <h2 className="font-serif font-semibold text-[16px] text-emerald-dark">Stock boost</h2>
            {boostActive && (
              <span className="text-[10px] font-semibold text-tint-dark bg-tint-emerald rounded-full px-1.5 py-0.5">
                Active
              </span>
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

        <div className="flex flex-col gap-2.5 bg-card rounded-2xl px-4 py-4 border border-border-hairline">
          <div className="flex items-center gap-1.5">
            <h2 className="font-serif font-semibold text-[16px] text-emerald-dark">Savings plans</h2>
            {activePlanCount > 0 && (
              <span className="text-[10px] font-semibold text-tint-dark bg-tint-emerald rounded-full px-1.5 py-0.5">
                {activePlanCount} active
              </span>
            )}
          </div>
          <p className="text-[13.5px] text-muted leading-relaxed">
            Offer your kid a place to set money aside and watch it grow. Set a monthly interest
            rate — flexible so they can take it out any time, or locked in for a fixed stretch.
          </p>
          <Link
            href="/home/settings/investing/savings-plans"
            className="bg-emerald text-white text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold"
          >
            Manage savings plans
          </Link>
        </div>
      </div>
    </div>
  );
}
