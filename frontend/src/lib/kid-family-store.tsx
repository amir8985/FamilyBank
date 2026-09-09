"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";
import { FamilyContext, type FamilyStore } from "@/lib/family-store";
import { clearResourceCache } from "@/lib/use-cached-resource";
import type { FamilyHome, KidMe, KidSummary, PortfolioOut } from "@/lib/types";

// The kid app's equivalent of FamilyProvider. A kid session sees exactly
// one kid — their own — so the `/home`-shaped store here is synthesized
// from that single kid's `/kids/{id}/portfolio` plus the identity from
// `/kid/me` (resolved server-side in the layout). Exposing the same
// `useFamily()` shape (FamilyStore) means every shared component —
// PortfolioClient, the buy/sell/savings flows, the history pages — works
// unchanged in both apps; only `token`, `basePath`/`isKid` differ. See
// CLAUDE.md "Kid login".

function num(value: string | number): number {
  return typeof value === "string" ? Number(value) : value;
}

function buildHome(identity: KidMe, portfolio: PortfolioOut | null): FamilyHome {
  const cash = portfolio ? num(portfolio.cash_available) : 0;
  const invested = portfolio ? num(portfolio.holdings_value) : 0;
  const kid: KidSummary = {
    // Use the opaque public_id as the kid id everywhere in the kid app —
    // URLs, cache keys, and API paths (the backend resolves it from the
    // session for a kid token). The real UUID never leaves /kid/me.
    id: identity.public_id,
    name: identity.name,
    avatar_color: identity.avatar_color,
    cash_balance: String(cash),
    portfolio_value: String(invested),
    portfolio_day_change_pct: portfolio?.total_day_change_pct ?? null,
  };
  return {
    base_currency: identity.base_currency,
    total_owed: String(cash),
    total_invested: String(invested),
    kids: [kid],
    prices_as_of: portfolio?.prices_as_of ?? null,
  };
}

export function KidFamilyProvider({
  identity,
  token,
  children,
}: {
  identity: KidMe;
  token: string | null;
  children: ReactNode;
}) {
  const [home, setHome] = useState<FamilyHome>(() => buildHome(identity, null));

  const tokenRef = useRef(token);
  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  const inflight = useRef<Promise<void> | null>(null);

  const refreshHome = useCallback(async () => {
    if (inflight.current) return inflight.current;
    const authToken = tokenRef.current;
    if (!authToken) return;
    const run = api
      .get<PortfolioOut>(`/kids/${identity.public_id}/portfolio`, authToken)
      .then((fresh) => setHome(buildHome(identity, fresh)))
      .catch(() => {
        // Leave the last-known values; a later refresh corrects them.
      })
      .finally(() => {
        inflight.current = null;
      });
    inflight.current = run;
    return run;
  }, [identity]);

  useEffect(() => {
    refreshHome();
  }, [refreshHome]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") refreshHome();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [refreshHome]);

  const applyKidBalanceDelta = useCallback((_kidId: string, delta: number) => {
    const shift = (d: number) =>
      setHome((h) => ({
        ...h,
        total_owed: String(num(h.total_owed) + d),
        kids: h.kids.map((k) => ({ ...k, cash_balance: String(num(k.cash_balance) + d) })),
      }));
    shift(delta);
    return () => shift(-delta);
  }, []);

  const unsupported = useCallback(() => {
    throw new Error("Not available in the kid app");
  }, []);

  const store = useMemo<FamilyStore>(
    () => ({
      home,
      token: token ?? null,
      basePath: "/kid",
      isKid: true,
      refreshHome,
      applyKidBalanceDelta,
      addKidOptimistic: () => {
        unsupported();
        return { tempId: "", rollback: () => {} };
      },
      removeKidOptimistic: () => {
        unsupported();
        return () => {};
      },
      applyCurrencyOptimistic: () => {
        unsupported();
        return () => {};
      },
    }),
    [home, token, refreshHome, applyKidBalanceDelta, unsupported]
  );

  return <FamilyContext.Provider value={store}>{children}</FamilyContext.Provider>;
}

export function resetKidCaches() {
  clearResourceCache();
}
