"use client";

import { useState } from "react";

// The frontend version is always shown (it ships in this bundle, no
// fetch). The running API version sits one tap below it — deliberately
// hidden by default so the footer stays a single quiet line for the
// people who never care which backend build they're on. Tapping the
// version toggles it: tap to reveal, tap again to hide.
export function AppVersion({ clientVersion }: { clientVersion: string }) {
  const [serverVersion, setServerVersion] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  async function toggle() {
    const next = !expanded;
    setExpanded(next);
    if (!next || serverVersion !== null) return;
    try {
      const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";
      const res = await fetch(`${base}/health`, { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      const body = await res.json();
      setServerVersion(typeof body.version === "string" ? body.version : "unknown");
    } catch {
      setServerVersion("unavailable");
    }
  }

  const serverLabel =
    serverVersion === null
      ? "…"
      : /^\d/.test(serverVersion)
        ? `v${serverVersion}`
        : serverVersion;

  return (
    <div className="text-center text-[12px] text-muted pb-6">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={expanded}
        aria-controls="app-server-version"
        className="underline decoration-dotted underline-offset-2"
      >
        v{clientVersion}
      </button>
      {expanded && (
        <div id="app-server-version" className="mt-0.5 text-[11.5px] text-muted/70">
          server {serverLabel}
        </div>
      )}
    </div>
  );
}
