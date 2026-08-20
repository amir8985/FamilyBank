import { currencySymbol } from "@/lib/format";

export function Sparkline({
  history,
  nativeCurrency,
}: {
  history: { date: string; close: number }[];
  nativeCurrency: string;
}) {
  const points = history.slice(-30);
  if (points.length < 2) return null;

  const closes = points.map((p) => p.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const trendingUp = points[points.length - 1].close >= points[0].close;
  const sym = currencySymbol(nativeCurrency);

  const startLabel = new Date(points[0].date).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const endLabel = new Date(points[points.length - 1].date).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });

  return (
    <div className="mt-3.5">
      <div className="flex items-end gap-1 h-14">
        {points.map((p) => {
          const heightPct = 15 + ((p.close - min) / range) * 80;
          return (
            <div
              key={p.date}
              className={`flex-1 rounded-sm ${trendingUp ? "bg-brass" : "bg-tint-emerald"}`}
              style={{ height: `${heightPct}%` }}
            />
          );
        })}
      </div>
      <div className="flex justify-between text-[11.5px] text-muted mt-1">
        <span>
          {startLabel} – {endLabel}
        </span>
        <span>
          {sym}
          {min.toFixed(2)} – {sym}
          {max.toFixed(2)}
        </span>
      </div>
    </div>
  );
}
