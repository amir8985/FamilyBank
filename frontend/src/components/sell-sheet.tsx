"use client";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { SellControls } from "@/components/sell-controls";
import { useFamily } from "@/lib/family-store";
import { invalidateKid } from "@/lib/use-cached-resource";
import { formatMoney, trimUnits } from "@/lib/format";
import type { HoldingOut } from "@/lib/types";

// Caller mounts this only while the sheet should be visible (see
// portfolio-client.tsx), so each open is a fresh mount — no reset effect needed.
export function SellSheet({
  onClose,
  kidId,
  holding,
  cashAvailable,
  currency,
}: {
  onClose: () => void;
  kidId: string;
  holding: HoldingOut;
  cashAvailable: number;
  currency: string;
}) {
  const { refreshHome } = useFamily();

  return (
    <BottomSheet onClose={onClose}>
      <h2 className="font-serif font-semibold text-[20px] text-emerald-dark">
        Sell {holding.display_name}
      </h2>
      <p className="text-[12.5px] text-muted -mt-3">
        You hold {trimUnits(holding.units)} units, worth {formatMoney(holding.current_value, currency)}.
      </p>

      <SellControls
        kidId={kidId}
        holding={holding}
        cashAvailable={cashAvailable}
        currency={currency}
        onSold={() => {
          onClose();
          // Client store reconcile instead of router.refresh() — the
          // screens that read this data are client-rendered from cache now.
          invalidateKid(kidId);
          refreshHome();
        }}
      />
    </BottomSheet>
  );
}
