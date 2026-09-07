"use client";

import { useEffect } from "react";
import Link from "next/link";

/** Shared content for every route segment's error.tsx (error boundaries
 * must be Client Components — see Next's file-conventions/error docs).
 * This is what a parent/kid actually sees if the backend is down, slow
 * past its own timeout, or throws — instead of navigating into a blank
 * or crashed screen, which was the previous behavior with no error
 * boundaries anywhere in the app. */
export function ErrorState({
  error,
  retry,
  homeHref = "/home",
}: {
  error: Error & { digest?: string };
  retry: () => void;
  homeHref?: string;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col items-center justify-center px-6 text-center gap-4">
      <div className="w-14 h-14 rounded-full bg-tint-negative flex items-center justify-center">
        <span className="text-negative text-2xl leading-none">!</span>
      </div>
      <h1 className="font-serif font-semibold text-[20px] text-emerald-dark">Something went wrong</h1>
      <p className="text-[14px] text-muted leading-[1.5] max-w-[300px]">
        We couldn&apos;t reach the server. This is usually temporary — check your connection and try
        again in a moment.
      </p>
      <div className="flex items-center gap-3 mt-1">
        <button
          onClick={() => retry()}
          className="min-h-11 px-6 rounded-lg bg-emerald text-cream text-[14px] font-semibold cursor-pointer"
        >
          Try again
        </button>
        <Link
          href={homeHref}
          className="min-h-11 flex items-center px-4 text-[14px] font-medium text-muted-strong"
        >
          Back to home
        </Link>
      </div>
    </div>
  );
}
