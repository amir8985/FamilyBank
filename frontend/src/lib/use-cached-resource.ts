"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";

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

function emit() {
  for (const l of listeners) l();
}

/** Wipe everything — call on sign-out so a different account never reads
 * the previous one's cached data from this tab. */
export function clearResourceCache() {
  cache.clear();
  inflight.clear();
  errors.clear();
  emit();
}

/** Drop one key (or a prefix, e.g. after a write that invalidates a
 * family-wide view). */
export function invalidateResource(keyOrPrefix: string) {
  for (const key of [...cache.keys()]) {
    if (key === keyOrPrefix || key.startsWith(keyOrPrefix)) cache.delete(key);
  }
  for (const key of [...errors.keys()]) {
    if (key === keyOrPrefix || key.startsWith(keyOrPrefix)) errors.delete(key);
  }
  emit();
}

export type CachedResource<T> = {
  data: T | undefined;
  error: Error | null;
  /** A background revalidation is in flight (data is already shown). */
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
  const [, rerender] = useReducer((n: number) => n + 1, 0);

  // Keep the latest fetcher without making it a dependency — callers pass
  // an inline closure, so its identity changes every render.
  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    listeners.add(rerender);
    return () => {
      listeners.delete(rerender);
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

  useEffect(() => {
    if (!key) return;
    const entry = cache.get(key);
    if (!entry || Date.now() - entry.ts > ttlMs) revalidate();
  }, [key, ttlMs, revalidate]);

  const mutate = useCallback(
    (updater: (prev: T | undefined) => T) => {
      if (!key) return () => {};
      const prev = cache.get(key);
      cache.set(key, {
        data: updater(prev?.data as T | undefined),
        ts: prev?.ts ?? Date.now(),
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
  return {
    data: entry?.data as T | undefined,
    error: key ? (errors.get(key) ?? null) : null,
    isValidating: key ? inflight.has(key) : false,
    revalidate,
    mutate,
  };
}
