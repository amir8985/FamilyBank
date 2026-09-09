"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import type { KidInviteResult, KidInviteStatus } from "@/lib/types";

// Parent-side: generate a kid's invite — a shareable link plus a short
// PIN the parent reads aloud. The link alone is useless without the PIN.
// It's multi-use for 24h (phone + laptop). See CLAUDE.md "Kid login".
export function AttachChildSheet({
  kidId,
  kidName,
  onClose,
}: {
  kidId: string;
  kidName: string;
  onClose: () => void;
}) {
  const { data: session } = useSession();
  const toast = useToast();
  const token = session?.backendToken;

  const [status, setStatus] = useState<KidInviteStatus | null>(null);
  const [invite, setInvite] = useState<KidInviteResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<null | "generate" | "signout">(null);
  const [copied, setCopied] = useState(false);

  const loadStatus = useCallback(() => {
    if (!token) return;
    api
      .get<KidInviteStatus>(`/kids/${kidId}/invite`, token)
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, [token, kidId]);
  useEffect(loadStatus, [loadStatus]);

  async function generate() {
    if (!token || busy) return;
    setBusy("generate");
    try {
      setInvite(await api.post<KidInviteResult>(`/kids/${kidId}/invite`, token));
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn't create a link", "error");
    } finally {
      setBusy(null);
    }
  }

  async function signOutAll() {
    if (!token || busy) return;
    if (!confirm(`Sign ${kidName} out on every device? They'll need a new link to get back in.`)) return;
    setBusy("signout");
    try {
      await api.post(`/kids/${kidId}/sign-out-all`, token);
      toast(`${kidName} was signed out everywhere.`, "info");
      setInvite(null);
      loadStatus();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn't sign them out", "error");
    } finally {
      setBusy(null);
    }
  }

  async function copyLink() {
    if (!invite) return;
    try {
      await navigator.clipboard.writeText(invite.claim_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast("Couldn't copy — select and copy the link manually", "error");
    }
  }

  async function share() {
    if (!invite || typeof navigator.share !== "function") return;
    try {
      await navigator.share({
        title: `${kidName}'s FamilyBank link`,
        text: "Open this to sign in to FamilyBank, then I'll tell you the PIN:",
        url: invite.claim_url,
      });
    } catch {
      /* share sheet cancelled */
    }
  }

  const canShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  return (
    <BottomSheet onClose={onClose}>
      <h2 className="font-serif font-semibold text-[20px] text-emerald-dark">Link a device</h2>

      {!invite && (
        <>
          <p className="text-[13.5px] leading-relaxed text-muted-strong -mt-2">
            Creates a link and a short PIN for {kidName}. Send them the link, then tell them the PIN
            out loud — the link alone won&apos;t work. It stays usable for <strong>24 hours</strong>,
            so they can open it on their phone and their computer. After that they&apos;re signed in
            for good on those devices.
          </p>
          {!loading && status?.has_pending_invite && (
            <p className="text-[12.5px] text-muted -mt-1">
              A link is already active for {kidName}. Making a new one replaces it (devices already
              signed in stay signed in).
            </p>
          )}
          <button
            type="button"
            disabled={busy !== null}
            onClick={generate}
            className="bg-emerald text-white text-center min-h-11 py-[15px] rounded-xl text-[15px] font-semibold disabled:opacity-50 cursor-pointer"
          >
            {busy === "generate" ? "Creating…" : status?.has_pending_invite ? "Create a new link" : "Create a link"}
          </button>
          {!loading && status?.sessions_active && (
            <button
              type="button"
              disabled={busy !== null}
              onClick={signOutAll}
              className="text-center min-h-11 py-3 rounded-xl text-[13.5px] font-semibold border border-negative text-negative disabled:opacity-50 cursor-pointer"
            >
              {busy === "signout" ? "Signing out…" : `Sign ${kidName} out of all devices`}
            </button>
          )}
        </>
      )}

      {invite && (
        <>
          <div className="flex flex-col gap-1">
            <span className="text-[12px] font-semibold text-muted">PIN — read this to {kidName}</span>
            <div className="font-serif font-semibold text-[32px] tracking-[0.3em] text-emerald text-center bg-cream rounded-xl py-3">
              {invite.pin}
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-[12px] font-semibold text-muted">Link — send this to {kidName}</span>
            <div className="text-[12.5px] text-muted-strong break-all bg-cream rounded-[10px] px-3 py-2.5">
              {invite.claim_url}
            </div>
          </div>

          <div className="flex gap-2.5">
            <button
              type="button"
              onClick={copyLink}
              className="flex-1 text-center min-h-11 py-3 rounded-xl text-[14px] font-semibold border border-border-hairline-strong text-emerald-dark cursor-pointer"
            >
              {copied ? "Copied ✓" : "Copy link"}
            </button>
            {canShare && (
              <button
                type="button"
                onClick={share}
                className="flex-1 bg-emerald text-white text-center min-h-11 py-3 rounded-xl text-[14px] font-semibold cursor-pointer"
              >
                Share
              </button>
            )}
          </div>

          <p className="text-[12px] text-muted">
            Works for 24 hours, on as many of {kidName}&apos;s devices as they need. To sign them out
            (a lost phone), reopen this and use &ldquo;Sign {kidName} out of all devices&rdquo;.
          </p>
        </>
      )}
    </BottomSheet>
  );
}
