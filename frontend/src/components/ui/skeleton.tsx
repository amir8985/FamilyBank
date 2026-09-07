/** A pulsing placeholder block for loading.tsx screens — App Router
 * shows these instantly on navigation (see loading.tsx file convention)
 * while the real Server Component data is still being fetched, so a
 * slow or unresponsive backend never leaves the user staring at a
 * frozen screen. Keep shapes loose (rounded blocks sized like the real
 * content) rather than exact pixel matches — that's all Next's own
 * guidance asks for. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-tint-neutral ${className}`} />;
}
