import { formatMoney } from "@/lib/format";

// A lot's whole synthetic trajectory since purchase, one point per real
// price tick (see backend/app/services/boost_service.py — the same walk
// that produces the headline current_value also produces every point
// here, so the chart and the number can never disagree).
export function LotChart({
  series,
  currency,
}: {
  series: { observed_at: string; value: string }[];
  currency: string;
}) {
  if (series.length < 2) {
    return (
      <div className="mt-3 h-32 flex items-center justify-center text-[12.5px] text-muted bg-cream rounded-2xl">
        No price update yet since this was bought — check back in a few hours.
      </div>
    );
  }

  const values = series.map((p) => Number(p.value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const width = 100;
  const height = 40;
  const coords = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - ((v - min) / range) * height;
    return [x, y] as const;
  });
  const linePath = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
  const areaPath = `${linePath} L${width},${height} L0,${height} Z`;

  const trendingUp = values[values.length - 1] >= values[0];
  const lineColor = trendingUp ? "var(--color-positive)" : "var(--color-negative)";

  const startLabel = new Date(series[0].observed_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
  const endLabel = new Date(series[series.length - 1].observed_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });

  return (
    <div className="mt-3">
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="w-full h-32">
        <path d={areaPath} fill={lineColor} opacity={0.08} />
        <path d={linePath} fill="none" stroke={lineColor} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="flex justify-between text-[11.5px] text-muted mt-1">
        <span>{startLabel} – {endLabel}</span>
        <span>
          {formatMoney(min, currency)} – {formatMoney(max, currency)}
        </span>
      </div>
    </div>
  );
}
