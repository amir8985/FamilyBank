export function TickerBadge({ symbol, size = 40 }: { symbol: string; size?: number }) {
  const fontSize = symbol.length > 5 ? size * 0.22 : size * 0.3;
  return (
    <div
      className="shrink-0 rounded-[10px] bg-tint-emerald flex items-center justify-center font-bold text-emerald px-1"
      style={{ width: size, height: size, fontSize }}
    >
      {symbol}
    </div>
  );
}
