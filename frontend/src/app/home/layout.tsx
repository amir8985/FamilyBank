import { requireSession } from "@/lib/session";

export default async function HomeLayout({ children }: LayoutProps<"/home">) {
  await requireSession();
  return <div className="min-h-screen bg-cream">{children}</div>;
}
