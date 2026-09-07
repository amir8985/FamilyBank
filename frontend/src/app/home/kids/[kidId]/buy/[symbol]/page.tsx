import { notFound } from "next/navigation";
import { requireSession } from "@/lib/session";
import { api, ApiError } from "@/lib/api";
import { BuyFormClient } from "@/components/buy-form-client";
import type { AssetDetailOut, FamilySettings, PortfolioOut } from "@/lib/types";

export default async function BuyPage({
  params,
  searchParams,
}: {
  params: Promise<{ kidId: string; symbol: string }>;
  searchParams: Promise<{ from?: string }>;
}) {
  const { kidId, symbol } = await params;
  const { from } = await searchParams;
  const session = await requireSession();

  let asset: AssetDetailOut;
  let portfolio: PortfolioOut;
  let settings: FamilySettings;
  try {
    [asset, portfolio, settings] = await Promise.all([
      api.get<AssetDetailOut>(`/catalog/${symbol}`, session.backendToken),
      api.get<PortfolioOut>(`/kids/${kidId}/portfolio`, session.backendToken),
      // Fetched fresh, not from session.baseCurrency — see kids/[kidId]/page.tsx.
      api.get<FamilySettings>("/family/settings", session.backendToken),
    ]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  // Preserves which tab (My Investments vs Buy) the user came from, so
  // the back chevron returns them there instead of always resetting to
  // the default tab.
  const backTab = from === "buy" ? "buy" : "holdings";

  // A symbol can now match more than one holding — buy() never merges
  // separate purchases into one (see CLAUDE.md's boosted-stocks status
  // entry). Used only for an informational "you already own N units"
  // line here — this screen never offers a sell action for any of them
  // (a lot has its own dedicated page reached from My Investments; a
  // legacy avg-cost holding is the one exception below).
  const matchingHoldings = portfolio.holdings.filter((h) => h.symbol === symbol);

  // The one remaining case this screen still sells directly: a
  // pre-lot legacy avg-cost holding (no lot_id, so it has no dedicated
  // detail page of its own) reached by tapping it in My Investments —
  // portfolio-client.tsx only sends that arrival here for a legacy
  // holding; every lot-based one goes straight to /lots/[lotId] and
  // never reaches this screen via "holdings" at all.
  const sellableHolding =
    from === "holdings" ? (matchingHoldings.find((h) => !h.lot_id) ?? null) : null;

  return (
    <BuyFormClient
      key={asset.symbol}
      kidId={kidId}
      kidName={portfolio.kid_name}
      asset={asset}
      currency={settings.base_currency}
      cashAvailable={Number(portfolio.cash_available)}
      backHref={`/home/kids/${kidId}?tab=${backTab}`}
      matchingHoldings={matchingHoldings}
      sellableHolding={sellableHolding}
      boostBufferRate={settings.boost_buffer_rate}
    />
  );
}
