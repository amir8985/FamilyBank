"use client";

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  variant = "card",
}: {
  options: { value: T; label: string; activeClassName?: string }[];
  value: T;
  onChange: (value: T) => void;
  /** "card": white shadowed pill (tabs, amount/units). "filled": solid
   * emerald pill (add/deduct) — matches the two distinct styles in the
   * design handoff. An option's own `activeClassName` overrides this
   * (e.g. Deduct going red instead of emerald when selected). */
  variant?: "card" | "filled";
}) {
  const activeClass =
    variant === "filled"
      ? "bg-emerald text-white"
      : "bg-card text-emerald shadow-[0_1px_3px_rgba(0,0,0,.08)]";

  return (
    <div className="flex bg-tint-neutral rounded-[10px] p-1">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`flex-1 min-h-11 text-center py-2.5 rounded-lg text-[13.5px] font-semibold transition-colors cursor-pointer ${
            opt.value === value ? (opt.activeClassName ?? activeClass) : "text-muted-strong"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
