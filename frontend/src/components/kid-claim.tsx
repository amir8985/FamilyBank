"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Logo } from "@/components/ui/logo";

export function KidClaim({ claimToken }: { claimToken: string }) {
  const router = useRouter();
  const [pin, setPin] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (pin.length < 4 || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/kid/api/claim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ claim_token: claimToken, pin }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.public_id) {
        setError(data.error ?? "Couldn't sign you in. Ask a parent for a new link.");
        setSubmitting(false);
        return;
      }
      // The claim response already set the httpOnly cookie; refresh so the
      // kid layout re-runs on the server and sees it, then land on home.
      router.refresh();
      router.replace(`/kid/kids/${data.public_id}`);
    } catch {
      setError("Something went wrong. Check your connection and try again.");
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-cream flex flex-col items-center justify-center px-8 gap-5">
      <Logo size={40} />
      <div className="text-center">
        <h1 className="font-serif font-semibold text-[22px] text-emerald-dark">Enter your PIN</h1>
        <p className="text-[13.5px] text-muted-strong mt-1.5 max-w-xs">
          Type the {" "}
          <span className="font-semibold">6-digit PIN</span> a parent read out to you.
        </p>
      </div>

      <form onSubmit={submit} className="w-full max-w-xs flex flex-col gap-3">
        <input
          autoFocus
          inputMode="numeric"
          autoComplete="one-time-code"
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 8))}
          placeholder="––––––"
          className="w-full text-center tracking-[0.5em] font-serif font-semibold text-[30px] text-emerald bg-card border border-border-hairline-strong rounded-xl py-3 outline-none focus:border-emerald placeholder:text-emerald/25 placeholder:tracking-[0.3em]"
        />
        {error && <p className="text-[13px] text-negative text-center">{error}</p>}
        <button
          type="submit"
          disabled={pin.length < 4 || submitting}
          className="bg-emerald text-white text-center min-h-11 py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p className="text-[12px] text-muted text-center max-w-xs">
        After this you won&apos;t need the PIN again on this device.
      </p>
    </div>
  );
}
