import { KidClaim } from "@/components/kid-claim";

export default async function KidJoinPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <KidClaim claimToken={token} />;
}
