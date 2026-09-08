"use client";

import { useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { TickerBadge } from "@/components/ui/ticker-badge";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Money } from "@/components/ui/money";
import { Skeleton } from "@/components/ui/skeleton";
import { SavingsDepositSheet } from "@/components/savings-deposit-sheet";
import { SavingsKindBadge } from "@/components/ui/savings-badge";
import { useFamily } from "@/lib/family-store";
import { invalidateKid } from "@/lib/use-cached-resource";
import { api, ApiError } from "@/lib/api";
import { formatMoney, formatPct, trimUnits } from "@/lib/format";
import type {
  AssetOut,
  DepositablePlanOut,
  PortfolioOut,
  SavingsOverviewOut,
} from "@/lib/types";

type Tab = "holdings" | "buy" | "save";

function RowSkeletons() {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <Skeleton className="w-9 h-9 rounded-full" />
            <Skeleton className="h-4 w-28" />
          </div>
          <Skeleton className="h-4 w-16" />
        </div>
      ))}
    </>
  );
}

function unlockLabel(deposit: SavingsOverviewOut["deposits"][number]): string {
  if (!deposit.is_locked) return "Flexible";
  if (deposit.is_matured) return "Unlocked";
  if (!deposit.matures_at) return "Locked";
  const days = Math.max(1, Math.ceil((new Date(deposit.matures_at).getTime() - Date.now()) / 86_400_000));
  if (days < 31) return `Locked · ${days} day${days === 1 ? "" : "s"} left`;
  const months = Math.round(days / 30.44);
  return `Locked · ${months} month${months === 1 ? "" : "s"} left`;
}

function planTypeLine(plan: DepositablePlanOut): string {
  const rate = `${Number(plan.monthly_rate).toFixed(1)}%/mo · ≈ ${Number(plan.annual_rate).toFixed(1)}%/yr`;
  if (plan.lock_months <= 0) return `Flexible · ${rate}`;
  return `Locked ${plan.lock_months} mo · ${rate}`;
}

export function PortfolioClient({
  kidId,
  portfolio,
  savings,
  catalog,
  currency,
  initialTab,
  holdingsLoading = false,
  catalogLoading = false,
  savingsLoading = false,
}: {
  kidId: string;
  portfolio: PortfolioOut;
  savings: SavingsOverviewOut;
  catalog: AssetOut[];
  currency: string;
  initialTab: Tab;
  holdingsLoading?: boolean;
  catalogLoading?: boolean;
  savingsLoading?: boolean;
}) {
  const { data: session } = useSession();
  const { refreshHome } = useFamily();
  const [tab, setTab] = useState<Tab>(initialTab);
  const [sellingAll, setSellingAll] = useState(false);
  const [sellAllError, setSellAllError] = useState<string | null>(null);
  const [depositPlan, setDepositPlan] = useState<DepositablePlanOut | null>(null);

  const dayChangePct = formatPct(portfolio.total_day_change_pct);
  const isPositive = Number(portfolio.total_day_change_amount) >= 0;
  const hasInvestments = portfolio.holdings.length > 0;
  const hasSavings = savings.deposits.length > 0;
  const savingsValue = Number(savings.savings_value);

  async function handleSellEverything() {
    if (!session?.backendToken) return;
    if (!confirm(`Sell every stock ${portfolio.kid_name} owns? Savings aren't affected. This can't be undone.`)) return;
    setSellingAll(true);
    setSellAllError(null);
    try {
      await api.post(`/kids/${kidId}/sell-all`, session.backendToken);
      invalidateKid(kidId);
      refreshHome();
    } catch (e) {
      setSellAllError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setSellingAll(false);
    }
  }

  return (
    <div className="max-w-md mx-auto flex flex-col min-h-screen">
      <div className="pt-[58px] px-5 pb-1 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Link
            href="/home"
            aria-label="Back"
            className="w-[26px] h-[26px] flex items-center justify-center text-emerald text-lg"
          >
            ‹
          </Link>
          <h1 className="font-serif font-semibold text-[19px] text-emerald-dark">
            {portfolio.kid_name}&apos;s Investments &amp; Savings
          </h1>
        </div>
        <Link href={`/home/kids/${kidId}/investments-history`} className="text-[12.5px] font-semibold text-emerald">
          History
        </Link>
      </div>

      <div className="px-5 pt-3.5 pb-1">
        <div className="text-[13px] font-medium text-muted">Cash available</div>
        <div className="font-serif font-semibold text-[32px] text-emerald">
          <Money amount={portfolio.cash_available} currency={currency} />
        </div>
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 mt-1">
          <span className="text-[14px] font-medium text-muted-strong">
            {formatMoney(portfolio.holdings_value, currency)} invested
          </span>
          {dayChangePct && (
            <span className={`text-[13px] font-semibold ${isPositive ? "text-positive" : "text-negative"}`}>
              {dayChangePct}
            </span>
          )}
          {savingsValue > 0 && (
            <span className="text-[14px] font-medium text-muted-strong">
              · {formatMoney(savings.savings_value, currency)} saved
            </span>
          )}
        </div>
      </div>

      <div className="px-5 pt-2 pb-2">
        <SegmentedControl
          value={tab}
          onChange={setTab}
          options={[
            { value: "holdings", label: "Portfolio" },
            { value: "buy", label: "Invest" },
            { value: "save", label: "Save" },
          ]}
        />
      </div>

      <div className="flex-1 px-5 pt-2 pb-6 flex flex-col gap-2.5">
        {tab === "holdings" && (
          <>
            <h2 className="font-serif font-semibold text-[15px] text-emerald-dark pt-1">Savings</h2>
            {savings.deposits.map((d) => {
              const interest = Number(d.accrued_interest);
              return (
                <Link
                  key={d.deposit_id}
                  href={`/home/kids/${kidId}/savings/${d.deposit_id}`}
                  className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex items-center justify-between"
                >
                  <div className="flex flex-col items-start gap-1">
                    <div className="font-semibold text-[15px] text-emerald-dark">{d.plan_name}</div>
                    <SavingsKindBadge locked={d.is_locked && !d.is_matured} label={unlockLabel(d)} />
                  </div>
                  <div className="text-right">
                    <div className="font-semibold text-[15px] text-emerald-dark">
                      {formatMoney(d.current_value, currency)}
                    </div>
                    {interest > 0 && (
                      <div className="font-semibold text-[12.5px] text-positive">
                        +{formatMoney(interest, currency)} interest
                      </div>
                    )}
                  </div>
                </Link>
              );
            })}
            {!hasSavings && savingsLoading && <RowSkeletons />}
            {!hasSavings && !savingsLoading && (
              <p className="text-[13px] text-muted">
                Nothing saved yet — switch to Save to put some cash aside.
              </p>
            )}

            <h2 className="font-serif font-semibold text-[15px] text-emerald-dark pt-3">Investments</h2>
            {portfolio.holdings.map((h) => {
              const pct = formatPct(h.since_purchase_pct);
              const positive = Number(h.since_purchase_pct ?? 0) >= 0;
              const href = h.lot_id
                ? `/home/kids/${kidId}/lots/${h.lot_id}`
                : `/home/kids/${kidId}/buy/${h.symbol}?from=holdings`;
              return (
                <Link
                  key={h.lot_id ?? h.symbol}
                  href={href}
                  className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <TickerBadge symbol={h.symbol} />
                    <div>
                      <div className="font-semibold text-[15px] text-emerald-dark">
                        {h.display_name}
                        {h.is_boosted && (
                          <span className="ml-1.5 align-middle text-[10px] font-semibold text-tint-dark bg-tint-emerald rounded-full px-1.5 py-0.5">
                            Boosted
                          </span>
                        )}
                      </div>
                      <div className="text-[12.5px] text-muted">{trimUnits(h.units)} units</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold text-[15px] text-emerald-dark">
                      {formatMoney(h.current_value, currency)}
                    </div>
                    {pct && (
                      <div className={`font-semibold text-[12.5px] ${positive ? "text-positive" : "text-negative"}`}>
                        {pct} since bought
                      </div>
                    )}
                  </div>
                </Link>
              );
            })}

            {!hasInvestments && holdingsLoading && <RowSkeletons />}
            {!hasInvestments && !holdingsLoading && (
              <p className="text-[13px] text-muted">
                No investments yet — switch to Invest to get started.
              </p>
            )}

            {hasInvestments && (
              <>
                <button
                  type="button"
                  disabled={sellingAll}
                  onClick={handleSellEverything}
                  className="mt-1 text-center min-h-11 py-[13px] rounded-xl text-[14px] font-semibold border border-negative text-negative cursor-pointer disabled:opacity-50"
                >
                  {sellingAll
                    ? "Selling…"
                    : `Sell all investments for ${formatMoney(portfolio.holdings_value, currency)}`}
                </button>
                {sellAllError && <p className="text-[13px] text-negative -mt-1">{sellAllError}</p>}
              </>
            )}
          </>
        )}

        {tab === "buy" &&
          (catalog.length === 0 && catalogLoading ? (
            <RowSkeletons />
          ) : (
            <>
              <CatalogSection
                title="Baskets"
                subtitle="A slice of many companies at once — steadier, simpler."
                assets={catalog.filter((a) => a.kind === "basket")}
                kidId={kidId}
                currency={currency}
              />
              <CatalogSection
                title="Individual stocks"
                subtitle="One company at a time — more ups and downs."
                assets={catalog.filter((a) => a.kind === "stock")}
                kidId={kidId}
                currency={currency}
              />
            </>
          ))}

        {tab === "save" && (
          <>
            <p className="text-[13px] text-muted leading-relaxed pt-1">
              Move cash into a savings plan and it earns interest every day. Flexible plans come out
              any time; locked plans stay put until their term is up.
            </p>
            {(["flexible", "locked"] as const).map((group) => {
              const groupPlans = savings.plans.filter((p) =>
                group === "flexible" ? p.lock_months === 0 : p.lock_months > 0,
              );
              if (groupPlans.length === 0) return null;
              return (
                <div key={group} className="flex flex-col gap-2.5">
                  <h2 className="font-serif font-semibold text-[15px] text-emerald-dark pt-2">
                    {group === "flexible" ? "Flexible" : "Locked"}
                  </h2>
                  {groupPlans.map((plan) => (
                    <div
                      key={plan.id}
                      className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex items-center justify-between gap-3"
                    >
                      <div>
                        <div className="font-semibold text-[15px] text-emerald-dark">{plan.name}</div>
                        <div className="text-[12.5px] text-muted">{planTypeLine(plan)}</div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setDepositPlan(plan)}
                        className="shrink-0 bg-emerald text-white min-h-11 px-4 rounded-xl text-[13px] font-semibold cursor-pointer"
                      >
                        Put money in
                      </button>
                    </div>
                  ))}
                </div>
              );
            })}
            {savings.plans.length === 0 && savingsLoading && <RowSkeletons />}
            {savings.plans.length === 0 && !savingsLoading && (
              <p className="text-center text-[13px] text-muted pt-4">
                No savings plans yet — a parent can add them under Settings › Advanced investing &amp;
                savings.
              </p>
            )}
          </>
        )}
      </div>

      {depositPlan && (
        <SavingsDepositSheet
          kidId={kidId}
          plan={depositPlan}
          cashAvailable={Number(portfolio.cash_available)}
          currency={currency}
          onClose={() => setDepositPlan(null)}
        />
      )}
    </div>
  );
}

function CatalogSection({
  title,
  subtitle,
  assets,
  kidId,
  currency,
}: {
  title: string;
  subtitle: string;
  assets: AssetOut[];
  kidId: string;
  currency: string;
}) {
  if (assets.length === 0) return null;
  return (
    <div className="flex flex-col gap-2.5">
      <div className="pt-1">
        <h2 className="font-serif font-semibold text-[16px] text-emerald-dark">{title}</h2>
        <p className="text-[12px] text-muted">{subtitle}</p>
      </div>
      {assets.map((asset) => {
        const pct = formatPct(asset.day_change_pct);
        const positive = Number(asset.day_change_pct ?? 0) >= 0;
        return (
          <Link
            key={asset.symbol}
            href={`/home/kids/${kidId}/buy/${asset.symbol}?from=buy`}
            className="bg-card rounded-2xl px-4 py-3.5 border border-border-hairline flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <TickerBadge symbol={asset.symbol} />
              <div className="font-semibold text-[15px] text-emerald-dark">{asset.display_name}</div>
            </div>
            <div className="text-right">
              {asset.price ? (
                <>
                  <div className="font-semibold text-[15px] text-emerald-dark">
                    {formatMoney(asset.price, currency)}
                  </div>
                  {pct && (
                    <div className={`font-semibold text-[12.5px] ${positive ? "text-positive" : "text-negative"}`}>
                      {pct}
                    </div>
                  )}
                </>
              ) : (
                <div className="text-[12.5px] text-muted">price pending</div>
              )}
            </div>
          </Link>
        );
      })}
    </div>
  );
}
