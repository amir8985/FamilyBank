"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

// Minimal transient-message queue. Optimistic writes close their sheet
// immediately, so a later failure ("couldn't save — restored") has no
// inline spot to render — it surfaces here instead. Auto-dismisses.

type Tone = "error" | "info";
type ToastItem = { id: number; message: string; tone: Tone };

const ToastContext = createContext<(message: string, tone?: Tone) => void>(() => {});

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const show = useCallback((message: string, tone: Tone = "info") => {
    const id = nextId.current++;
    setToasts((prev) => [...prev, { id, message, tone }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4200);
  }, []);

  const value = useMemo(() => show, [show]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed inset-x-0 bottom-5 z-[100] flex flex-col items-center gap-2 px-4 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`max-w-md w-full rounded-xl px-4 py-3 text-[13.5px] font-medium shadow-[0_6px_20px_rgba(0,0,0,.18)] ${
              t.tone === "error" ? "bg-negative text-white" : "bg-emerald-dark text-cream"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
