"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// A tiny stale-while-revalidate cache for the per-kid detail data that
// isn't in the `/home` store (portfolio, catalog, asset detail, history
// lists). Navigating back to a screen shows its last data instantly and
// revalidates in the background; a cold screen shows a section skeleton
// while the first fetch runs. Deliberately hand-rolled and minimal — the
// project keeps its runtime dependency list to next/react/next-auth.
// See CLAUDE.md's 2026-09-07 "Instant UX" entry.

type Entry = { data: unknown; ts: number };

const cache = new Map<string, Entry>();
const inflight = new Map<string, Promise<unknown>>();
const errors = new Map<string, Error>();
const listeners = new Set<() => void>();

// Every mounted hook subscribes; a mutation re-renders all of them. Each
// hook also re-checks whether it needs to fetch on that re-render, so
// dropping a key (invalidateResource / clearResourceCache) makes the
// screens showing it refetch instead of sitting on an empty skeleton
// until the next navigation.
function emit() {
  for (const l of listeners) l();
}

/** Wipe everything — call on sign-out so a different account never reads
 * the previous one's cached data from this tab, and after a family-wide
 * change (currency, sell-and-rebuy) that touches every cached view. */
export function clearResourceCache() {
  cache.clear();
  inflight.clear();
  errors.clear();
  emit();
}

function dropMatching(prefixes: string[]) {
  for (const map of [cache, errors]) {
    for (const key of [...map.keys()]) {
      if (prefixes.some((p) => key === p || key.startsWith(p))) map.delete(key);
    }
  }
}

/** Drop one key, or every key under a `prefix` (used after a write that
 * invalidates a whole family/kid view). */
export function invalidateResource(keyOrPrefix: string) {
  dropMatching([keyOrPrefix]);
  emit();
}

/** Every cached resource that belongs to one kid — call after any write
 * that changes that kid's balance or holdings. One notification, not one
 * per key. */
export function invalidateKid(kidId: string) {
  dropMatching([
    `portfolio:${kidId}`,
    `debt:${kidId}`,
    `investment-transactions:${kidId}`,
    `lot:${kidId}:`,
  ]);
  emit();
}

export type CachedResource<T> = {
  data: T | undefined;
  error: Error | null;
  /** A background revalidation is in flight (data may already be shown). */
  isValidating: boolean;
  /** Force a refetch now. */
  revalidate: () => Promise<void>;
  /** Optimistically patch the cached value; returns a rollback. */
  mutate: (updater: (prev: T | undefined) => T) => () => void;
};

export function useCachedResource<T>(
  key: string | null,
  fetcher: () => Promise<T>,
  opts: { ttlMs?: number } = {}
): CachedResource<T> {
  const ttlMs = opts.ttlMs ?? 15_000;
  const [tick, setTick] = useState(0);

  // Keep the latest fetcher without making it a dependency — callers pass
  // an inline closure, so its identity changes every render.
  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    const onChange = () => setTick((t) => t + 1);
    listeners.add(onChange);
    return () => {
      listeners.delete(onChange);
    };
  }, []);

  const revalidate = useCallback(async () => {
    if (!key) return;
    const existing = inflight.get(key);
    if (existing) {
      await existing.catch(() => {});
      return;
    }
    const run = fetcherRef
      .current()
      .then((data) => {
        cache.set(key, { data, ts: Date.now() });
        errors.delete(key);
      })
      .catch((e: unknown) => {
        errors.set(key, e instanceof Error ? e : new Error(String(e)));
      })
      .finally(() => {
        inflight.delete(key);
        emit();
      });
    inflight.set(key, run);
    emit(); // reflect isValidating
    await run;
  }, [key]);

  // Fetch on mount, when the key changes, and whenever the cache is
  // mutated elsewhere (tick, bumped by emit) — the guard means a warm,
  // fresh entry costs only a Map lookup, not a request.
  useEffect(() => {
    if (!key) return;
    const entry = cache.get(key);
    if ((!entry || Date.now() - entry.ts > ttlMs) && !inflight.has(key)) {
      revalidate();
    }
  }, [key, ttlMs, revalidate, tick]);

  const mutate = useCallback(
    (updater: (prev: T | undefined) => T) => {
      if (!key) return () => {};
      const prev = cache.get(key);
      cache.set(key, {
        data: updater(prev?.data as T | undefined),
        // A mutate before the first real load must not mark the entry
        // fresh, or the initial fetch would be skipped.
        ts: prev?.ts ?? 0,
      });
      emit();
      return () => {
        if (prev) cache.set(key, prev);
        else cache.delete(key);
        emit();
      };
    },
    [key]
  );

  const entry = key ? cache.get(key) : undefined;
  const validating = key ? inflight.has(key) : false;
  return {
    data: entry?.data as T | undefined,
    // Suppress a stale error while a retry is in flight so a caller that
    // throws on `error` (routing to error.tsx) gets a chance to recover
    // instead of re-throwing on every remount.
    error: key && !validating ? (errors.get(key) ?? null) : null,
    isValidating: validating,
    revalidate,
    mutate,
  };
}
