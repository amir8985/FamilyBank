"use client";

import { signIn } from "next-auth/react";

export function SignInButton({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <button type="button" onClick={() => signIn("google", { callbackUrl: "/home" })} className={className}>
      {children}
    </button>
  );
}
