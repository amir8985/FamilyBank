"use client";

import { useEffect } from "react";

/** Mount/unmount this to show/hide it — callers conditionally render it
 * (e.g. `{target && <BottomSheet .../>}`) rather than passing an `open`
 * flag, so each open starts with fresh internal state. */
export function BottomSheet({
  onClose,
  children,
}: {
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <button
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/35 cursor-default"
      />
      <div className="relative w-full max-w-md bg-card rounded-t-[24px] px-[22px] pt-[22px] pb-7 flex flex-col gap-[18px] shadow-[0_-10px_30px_rgba(0,0,0,.2)] animate-[sheet-in_0.25s_ease-out]">
        <div className="w-9 h-1 rounded-full bg-black/15 self-center" />
        {children}
      </div>
      <style>{`
        @keyframes sheet-in {
          from { transform: translateY(24px); opacity: 0.6; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
