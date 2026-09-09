import { redirect } from "next/navigation";
import { listKidSessionIds, getLastKidId } from "@/lib/kid-session";

// The bare /kid entry point. There's no picker: it goes straight to the
// kid whose session this device last used (or the only one it has). Each
// kid keeps their own `/kid/kids/<handle>` link, so a shared family
// device just means each kid opens their own bookmark.
export default async function KidLanding() {
  const ids = await listKidSessionIds();
  if (ids.length === 0) redirect("/kid/locked");

  const last = await getLastKidId();
  const target = last && ids.includes(last) ? last : ids[0];
  redirect(`/kid/kids/${target}`);
}
