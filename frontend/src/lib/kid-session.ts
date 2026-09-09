import { cookies } from "next/headers";

// Per-kid httpOnly cookie holding that kid's backend session JWT. Keyed
// by the kid's opaque public_id (the value in every kid URL) so two kids
// on one shared device — or two tabs in one browser — don't clobber each
// other. Set by app/kid/api/claim, cleared by app/kid/api/signout.
const PREFIX = "kid_sess_";

// A non-httpOnly hint of the last kid used on this device, so bare `/kid`
// goes straight to the right one instead of showing a picker.
export const KID_LAST_COOKIE = "kid_last";

export const kidCookieName = (publicId: string) => `${PREFIX}${publicId}`;

export async function getKidToken(publicId: string): Promise<string | null> {
  const jar = await cookies();
  return jar.get(kidCookieName(publicId))?.value ?? null;
}

/** Every kid public_id this browser currently holds a session for. */
export async function listKidSessionIds(): Promise<string[]> {
  const jar = await cookies();
  return jar
    .getAll()
    .filter((c) => c.name.startsWith(PREFIX) && c.value)
    .map((c) => c.name.slice(PREFIX.length));
}

export async function getLastKidId(): Promise<string | null> {
  const jar = await cookies();
  return jar.get(KID_LAST_COOKIE)?.value ?? null;
}
