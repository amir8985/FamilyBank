import { Logo } from "@/components/ui/logo";

/** Shown when a kid has no valid session — either they never signed in on
 * this device, or their session was revoked (a parent generated and used
 * a new link). Deliberately not a scary error: re-linking is normal. */
export function KidLockedNotice({ revoked = false }: { revoked?: boolean }) {
  return (
    <div className="min-h-screen bg-cream flex flex-col items-center justify-center px-8 text-center gap-4">
      <Logo size={40} />
      <h1 className="font-serif font-semibold text-[22px] text-emerald-dark">
        {revoked ? "You've been signed out" : "You're not signed in"}
      </h1>
      <p className="text-[14px] leading-relaxed text-muted-strong max-w-xs">
        {revoked ? "A parent signed you out of all your devices. " : ""}
        Ask a parent to open FamilyBank, go to Settings → Link a device, and send you a fresh link.
        Open it on this device and enter the PIN they read out to you.
      </p>
    </div>
  );
}
