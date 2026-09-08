/** Tiny marker distinguishing a locked savings deposit from a flexible
 * one — a padlock (closed = locked, open = withdraw any time) plus a
 * soft tint. Kept small and low-contrast on purpose. */
export function SavingsKindBadge({ locked, label }: { locked: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full pl-1 pr-1.5 py-0.5 text-[11px] font-semibold ${
        locked ? "bg-tint-brass text-brass-dark" : "bg-tint-emerald text-tint-dark"
      }`}
    >
      <svg width="10" height="11" viewBox="0 0 10 11" fill="none" aria-hidden>
        <rect x="1" y="5" width="8" height="5.5" rx="1.2" fill="currentColor" />
        {locked ? (
          <path d="M2.6 5V3.4a2.4 2.4 0 0 1 4.8 0V5" stroke="currentColor" strokeWidth="1.1" />
        ) : (
          <path d="M2.6 5V3.4a2.4 2.4 0 0 1 4.8 0" stroke="currentColor" strokeWidth="1.1" />
        )}
      </svg>
      {label}
    </span>
  );
}
