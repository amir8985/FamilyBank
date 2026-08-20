export function Logo({ size = 30 }: { size?: number }) {
  return (
    <div className="flex items-center gap-2.5">
      <div
        className="rounded-full bg-emerald flex items-center justify-center border-2 border-brass"
        style={{ width: size, height: size }}
      >
        <span
          className="font-serif font-semibold text-brass"
          style={{ fontSize: size * 0.35 }}
        >
          FB
        </span>
      </div>
      <span className="font-serif font-semibold text-emerald-dark tracking-[-0.015em]" style={{ fontSize: size * 0.57 }}>
        FamilyBank
      </span>
    </div>
  );
}
