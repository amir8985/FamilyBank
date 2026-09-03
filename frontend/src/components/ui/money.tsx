import { formatMoneyParts } from "@/lib/format";

/** Renders a currency amount with the symbol split into its own
 * font-sans span, so it stays legible under a font-serif ancestor that
 * lacks the glyph (e.g. ₪ in Source Serif 4). */
export function Money({
  amount,
  currency,
  className,
}: {
  amount: string | number;
  currency: string;
  className?: string;
}) {
  const { before, symbol, after } = formatMoneyParts(amount, currency);
  return (
    <span className={className}>
      {before}
      <span className="font-sans">{symbol}</span>
      {after}
    </span>
  );
}
