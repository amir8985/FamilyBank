export function Sparkline({ history }: { history: { date: string; close: number }[] }) {
  const points = history.slice(-7);
  if (points.length === 0) return null;

  const closes = points.map((p) => p.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;

  return (
    <div className="flex items-end gap-1 h-14 mt-3.5">
      {points.map((p, i) => {
        const heightPct = 25 + ((p.close - min) / range) * 70;
        const up = i === 0 || p.close >= points[i - 1].close;
        return (
          <div
            key={p.date}
            className={`flex-1 rounded-sm ${up ? "bg-brass" : "bg-tint-emerald"}`}
            style={{ height: `${heightPct}%` }}
          />
        );
      })}
    </div>
  );
}
