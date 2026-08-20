"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { api, ApiError } from "@/lib/api";
import type { KidSummary } from "@/lib/types";

// Caller mounts this only while the sheet should be visible (see home-client.tsx).
export function AddKidSheet({ onClose }: { onClose: () => void }) {
  const { data: session } = useSession();
  const router = useRouter();
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    if (!session?.backendToken || !name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.post<KidSummary>("/kids", session.backendToken, { name: name.trim() });
      setName("");
      onClose();
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
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

      {error && <p className="text-[13px] text-negative">{error}</p>}

      <button
        type="button"
        disabled={submitting || !name.trim()}
        onClick={handleConfirm}
        className="bg-emerald text-white text-center py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
      >
        {submitting ? "Adding…" : "Add kid"}
      </button>
    </BottomSheet>
  );
}
