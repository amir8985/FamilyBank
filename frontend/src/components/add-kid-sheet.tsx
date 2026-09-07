"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { useFamily } from "@/lib/family-store";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import type { KidSummary } from "@/lib/types";

// Caller mounts this only while the sheet should be visible (see settings-form.tsx).
export function AddKidSheet({ onClose }: { onClose: () => void }) {
  const { data: session } = useSession();
  const { addKidOptimistic, refreshHome } = useFamily();
  const toast = useToast();
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function handleConfirm() {
    const trimmed = name.trim();
    if (!session?.backendToken || !trimmed || submitting) return;
    setSubmitting(true);

    const token = session.backendToken;
    const { rollback } = addKidOptimistic(trimmed);
    onClose();

    api
      .post<KidSummary>("/kids", token, { name: trimmed })
      .then(() => refreshHome())
      .catch((e) => {
        rollback();
        const msg =
          e instanceof ApiError && e.status < 500
            ? e.message
            : `Couldn't add ${trimmed} — please try again.`;
        toast(msg, "error");
      });
  }

  return (
    <BottomSheet onClose={onClose}>
      <h2 className="font-serif font-semibold text-[20px] text-emerald-dark">Add a kid</h2>

      <label className="flex flex-col gap-1.5">
        <span className="text-[12px] font-semibold text-muted">Name</span>
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Maya"
          maxLength={60}
          className="border border-border-hairline-strong rounded-[10px] px-3.5 py-3 text-[14.5px] text-emerald-dark outline-none focus:border-emerald"
        />
      </label>

      <button
        type="button"
        disabled={submitting || !name.trim()}
        onClick={handleConfirm}
        className="bg-emerald text-white text-center min-h-11 py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        Add kid
      </button>
    </BottomSheet>
  );
}
