import { KidLockedNotice } from "@/components/kid-locked-notice";

export default async function KidLockedPage({
  searchParams,
}: {
  searchParams: Promise<{ revoked?: string }>;
}) {
  const { revoked } = await searchParams;
  return <KidLockedNotice revoked={revoked === "1"} />;
}
