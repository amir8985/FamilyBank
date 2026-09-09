import { NextRequest, NextResponse } from "next/server";
import { kidCookieName } from "@/lib/kid-session";

export async function POST(req: NextRequest) {
  const { publicId } = (await req.json().catch(() => ({}))) as { publicId?: string };
  const out = NextResponse.json({ ok: true });
  if (publicId) {
    out.cookies.set(kidCookieName(publicId), "", {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 0,
    });
  }
  return out;
}
