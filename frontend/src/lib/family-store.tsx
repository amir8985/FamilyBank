"use client";

import {
  Component,
  Suspense,
  createContext,
  use,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useSession } from "next-auth/react";
import { api } from "@/lib/api";
import { HomeSkeleton } from "@/components/skeletons";
import { ErrorState } from "@/components/ui/error-state";
import { clearResourceCache } from "@/lib/use-cached-resource";
import type { FamilyHome, KidSummary } from "@/lib/types";

// The whole `/home` payload, held client-side for the session so that
// navigating between screens that only need this data (Home, Settings,
// and the header/cash shell of a kid's page) is instant instead of a
// server round-trip each time. Seeded once from a server-started request
// (see `home/layout.tsx`), then owned by the client: writes update it
// optimistically and a background `/home` refetch reconciles it against
// server truth. See CLAUDE.md's 2026-09-07 "Instant UX" entry.

export type FamilyStore = {
  home: FamilyHome;
  /** Backend session token for API calls — the parent's NextAuth-issued
   * token here; the kid's session token in KidFamilyProvider. Shared
   * components read it from here instead of `useSession()` so the same
   * component works in both the parent app and the kid app. */
  token: string | null;
  /** Root of the current app: `/home` (parent) or `/kid` (kid). Shared
   * components build per-kid hrefs from this — prefer the `useKidLinks`
   * helper below over touching it directly. */
  basePath: string;
  /** True inside the kid app. Changes where "home" and "portfolio" links
   * point (the kid's home is `/kid/kids/<id>`, not `/kid`). */
  isKid: boolean;
  /** Refetch `/home` and replace the store with server truth. Deduped —
   * concurrent calls share one request. */
  refreshHome: () => Promise<void>;
  /** Optimistically add `delta` (signed, in the family's currency) to a
   * kid's cash balance and the family total. Returns a rollback that
   * applies the inverse, so it composes safely with other in-flight
   * optimistic writes. */
  applyKidBalanceDelta: (kidId: string, delta: number) => () => void;
  /** Optimistically append a kid. Returns the temp id (so the caller can
   * swap it once the real row arrives) and an inverse rollback. */
  addKidOptimistic: (name: string) => { tempId: string; rollback: () => void };
  /** Optimistically remove a kid. Rollback re-inserts it at its original
   * position. */
  removeKidOptimistic: (kidId: string) => () => void;
  /** Optimistically apply a currency change: swap `base_currency` and set
   * each kid's already-converted balance. Rollback restores the snapshot
   * (currency change is a big, human-paced action — concurrent ones
   * aren't a realistic concern). */
  applyCurrencyOptimistic: (
    currency: string,
    convertedBalancesByKidId: Record<string, number>
  ) => () => void;
};

export const FamilyContext = createContext<FamilyStore | null>(null);

export function useFamily(): FamilyStore {
  const ctx = useContext(FamilyContext);
  if (!ctx) throw new Error("useFamily must be used within a FamilyProvider");
  return ctx;
}

/** Resolve the in-app hrefs for one kid, correct for whichever app
 * (parent or kid) the calling component is rendering in:
 *  - `pagePrefix`  — base for sub-pages: `${pagePrefix}/buy/AAPL`, `/history`, `/lots/x`, `/savings/x`
 *  - `portfolio`   — that kid's portfolio screen
 *  - `home`        — the "up and out" target (parent: the family home; kid: their own home)
 */
export function useKidLinks(kidId: string) {
  const { basePath, isKid } = useFamily();
  const pagePrefix = `${basePath}/kids/${kidId}`;
  return {
    pagePrefix,
    portfolio: isKid ? `${pagePrefix}/portfolio` : pagePrefix,
    home: isKid ? pagePrefix : basePath,
  };
}

// Mirrors backend AVATAR_PALETTE (app/models/kid.py) — kept in sync so an
// optimistically-added kid's avatar doesn't change color when the real
// row arrives. The backend cycles by existing-kid count; so do we.
const AVATAR_PALETTE = ["amber", "teal", "violet", "rose", "sky", "lime"];

function num(value: string | number): number {
  return typeof value === "string" ? Number(value) : value;
}

function withKids(home: FamilyHome, kids: KidSummary[]): FamilyHome {
  return { ...home, kids };
}

export function FamilyProvider({
  homePromise,
  children,
}: {
  homePromise: Promise<FamilyHome>;
  children: ReactNode;
}) {
  return (
    <FamilySeedErrorBoundary>
      <Suspense fallback={<HomeSkeleton />}>
        <FamilyStoreRoot homePromise={homePromise}>{children}</FamilyStoreRoot>
      </Suspense>
    </FamilySeedErrorBoundary>
  );
}

function FamilyStoreRoot({
  homePromise,
  children,
}: {
  homePromise: Promise<FamilyHome>;
  children: ReactNode;
}) {
  // Suspends only on the first mount (React caches the resolved value of
  // this promise). The layout keeps this component mounted across every
  // in-segment navigation, so it never suspends again — `home` state
  // persists and downstream screens read it synchronously.
  const seeded = use(homePromise);
  const [home, setHome] = useState<FamilyHome>(seeded);

  const { data: session } = useSession();
  const token = session?.backendToken;
  const tokenRef = useRef(token);
  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  const inflightRefresh = useRef<Promise<void> | null>(null);

  const refreshHome = useCallback(async () => {
    if (inflightRefresh.current) return inflightRefresh.current;
    const authToken = tokenRef.current;
    if (!authToken) return;
    const run = api
      .get<FamilyHome>("/home", authToken)
      .then((fresh) => {
        setHome(fresh);
      })
      .catch(() => {
        // A failed background reconcile leaves the optimistic value in
        // place; the next successful refresh (or navigation) corrects it.
      })
      .finally(() => {
        inflightRefresh.current = null;
      });
    inflightRefresh.current = run;
    return run;
  }, []);

  // Freshness nets for changes this tab didn't make — a kid trading in
  // their own app, or the parent acting in another tab. Reconcile when
  // the tab regains focus, and poll on a slow interval while it's
  // visible (paused while hidden so a backgrounded tab costs nothing).
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") refreshHome();
    };
    document.addEventListener("visibilitychange", onVisible);

    let timer: ReturnType<typeof setInterval> | null = null;
    const startPoll = () => {
      if (timer || document.visibilityState !== "visible") return;
      timer = setInterval(() => {
        if (document.visibilityState === "visible") refreshHome();
      }, 30_000);
    };
    const stopPoll = () => {
      if (timer) clearInterval(timer);
      timer = null;
    };
    const onVis = () => (document.visibilityState === "visible" ? startPoll() : stopPoll());
    document.addEventListener("visibilitychange", onVis);
    startPoll();

    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      document.removeEventListener("visibilitychange", onVis);
      stopPoll();
    };
  }, [refreshHome]);

  const applyKidBalanceDelta = useCallback((kidId: string, delta: number) => {
    const shift = (d: number) =>
      setHome((h) => ({
        ...h,
        total_owed: String(num(h.total_owed) + d),
        kids: h.kids.map((k) =>
          k.id === kidId ? { ...k, cash_balance: String(num(k.cash_balance) + d) } : k
        ),
      }));
    shift(delta);
    return () => shift(-delta);
  }, []);

  const addKidOptimistic = useCallback((name: string) => {
    const tempId = `temp-${crypto.randomUUID()}`;
    setHome((h) => {
      const color = AVATAR_PALETTE[h.kids.length % AVATAR_PALETTE.length];
      const tempKid: KidSummary = {
        id: tempId,
        name,
        avatar_color: color,
        cash_balance: "0",
        portfolio_value: "0",
        portfolio_day_change_pct: null,
      };
      return withKids(h, [...h.kids, tempKid]);
    });
    return {
      tempId,
      rollback: () =>
        setHome((h) => withKids(h, h.kids.filter((k) => k.id !== tempId))),
    };
  }, []);

  const removeKidOptimistic = useCallback(
    (kidId: string) => {
      const index = home.kids.findIndex((k) => k.id === kidId);
      const kid = index >= 0 ? home.kids[index] : null;
      setHome((h) => withKids(h, h.kids.filter((k) => k.id !== kidId)));
      return () => {
        if (!kid) return;
        setHome((h) => {
          if (h.kids.some((k) => k.id === kid.id)) return h;
          const kids = [...h.kids];
          kids.splice(Math.min(index, kids.length), 0, kid);
          return withKids(h, kids);
        });
      };
    },
    [home]
  );

  const applyCurrencyOptimistic = useCallback(
    (currency: string, convertedBalancesByKidId: Record<string, number>) => {
      const snapshot = home;
      setHome((h) => {
        const kids = h.kids.map((k) =>
          k.id in convertedBalancesByKidId
            ? { ...k, cash_balance: String(convertedBalancesByKidId[k.id]) }
            : k
        );
        return {
          ...h,
          base_currency: currency,
          kids,
          // total_owed converts exactly (sum of the new balances);
          // total_invested needs an FX rate we don't have here — the
          // background refreshHome() corrects it a beat later.
          total_owed: String(kids.reduce((sum, k) => sum + num(k.cash_balance), 0)),
        };
      });
      return () => setHome(snapshot);
    },
    [home]
  );

  const store = useMemo<FamilyStore>(
    () => ({
      home,
      token: token ?? null,
      basePath: "/home",
      isKid: false,
      refreshHome,
      applyKidBalanceDelta,
      addKidOptimistic,
      removeKidOptimistic,
      applyCurrencyOptimistic,
    }),
    [
      home,
      token,
      refreshHome,
      applyKidBalanceDelta,
      addKidOptimistic,
      removeKidOptimistic,
      applyCurrencyOptimistic,
    ]
  );

  return <FamilyContext.Provider value={store}>{children}</FamilyContext.Provider>;
}

/** Clears every client-side cache — call on sign-out so the next account
 * to use this browser tab never sees the previous one's data. */
export function resetClientCaches() {
  clearResourceCache();
  // The family store lives in component state; a full navigation on
  // sign-out (signOut({ callbackUrl }) does a hard load) unmounts it.
}

class FamilySeedErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <ErrorState
          error={this.state.error}
          retry={() => {
            this.setState({ error: null });
            window.location.reload();
          }}
        />
      );
    }
    return this.props.children;
  }
}
