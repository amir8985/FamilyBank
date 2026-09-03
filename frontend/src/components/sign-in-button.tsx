"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { BottomSheet } from "@/components/ui/bottom-sheet";

export function SignInButton({ className, children }: { className?: string; children: React.ReactNode }) {
  const [showConsent, setShowConsent] = useState(false);

  return (
    <>
      <button type="button" onClick={() => setShowConsent(true)} className={className}>
        {children}
      </button>
      {showConsent && (
        <ConsentSheet onClose={() => setShowConsent(false)} />
      )}
    </>
  );
}

function ConsentSheet({ onClose }: { onClose: () => void }) {
  const [agreed, setAgreed] = useState(false);

  return (
    <BottomSheet onClose={onClose}>
      <h3 className="font-serif font-semibold text-[19px] text-emerald-dark m-0">
        Before you continue
      </h3>
      <p className="text-[14.5px] leading-[1.6] text-muted-strong m-0">
        FamilyBank is a virtual allowance tracker — no real broker, no real money moves. Signing in
        creates a family account and stores whatever you enter about your kids (name, balance,
        virtual holdings).
      </p>
      <label className="flex items-start gap-2.5 text-[14px] leading-[1.5] text-emerald-dark cursor-pointer select-none">
        <input
          type="checkbox"
          checked={agreed}
          onChange={(e) => setAgreed(e.target.checked)}
          className="mt-0.5 w-[18px] h-[18px] shrink-0 accent-emerald cursor-pointer"
        />
        <span>
          I&apos;m a parent or guardian and I agree to the{" "}
          <a href="/privacy" target="_blank" className="text-emerald underline">
            Privacy Policy
          </a>{" "}
          and{" "}
          <a href="/terms" target="_blank" className="text-emerald underline">
            Terms of Service
          </a>
          .
        </span>
      </label>
      <button
        type="button"
        disabled={!agreed}
        onClick={() => signIn("google", { callbackUrl: "/home" })}
        className="bg-emerald text-cream px-6 py-[13px] rounded-[9px] text-[15px] font-semibold disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
      >
        Continue with Google
      </button>
    </BottomSheet>
  );
}
