import { NextRequest, NextResponse } from "next/server";
import { kidCookieName } from "@/lib/kid-session";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

// The kid claims their invite here: this handler forwards the claim token
// + PIN to the backend, and on success stashes the returned session JWT
// in a per-kid httpOnly cookie so every later visit is silent. The kid's
// browser never sees the raw token via this path — only the cookie.
export async function POST(req: NextRequest) {
  let body: { claim_token?: string; pin?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Bad request" }, { status: 400 });
  }

  const res = await fetch(`${BACKEND_URL}/kid-auth/claim`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ claim_token: body.claim_token, pin: body.pin }),
  });

  const data = (await res.json().catch(() => ({}))) as {
    detail?: string;
    session_token?: string;
    public_id?: string;
    kid_name?: string;
  };
  if (!res.ok || !data.session_token || !data.public_id) {
    return NextResponse.json({ error: data.detail ?? "Couldn't sign in" }, { status: res.status || 400 });
  }

  const out = NextResponse.json({ ok: true, public_id: data.public_id, kid_name: data.kid_name });
  out.cookies.set(kidCookieName(data.public_id), data.session_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 365, // matches the backend kid-JWT TTL
  });
  return out;
}
