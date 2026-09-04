import Link from "next/link";
import { Logo } from "@/components/ui/logo";

export function LegalPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col min-h-screen bg-cream text-emerald-dark">
      <nav className="flex items-center justify-between px-6 md:px-16 py-[18px] md:py-[22px] border-b border-border-hairline">
        <Link href="/">
          <Logo size={34} />
        </Link>
        <Link href="/" className="text-[14px] font-semibold text-emerald hover:underline">
          Back to home
        </Link>
      </nav>

      <main className="px-6 md:px-16 py-14 max-w-[760px] mx-auto w-full box-border flex flex-col gap-8">
        <div>
          <h1 className="font-serif font-semibold text-[32px] md:text-[40px] mb-2">{title}</h1>
          <p className="text-[14px] text-muted">Last updated: {updated}</p>
        </div>
        {children}
      </main>

      <footer className="px-6 md:px-16 py-10 flex items-center justify-between border-t border-border-hairline flex-wrap gap-4">
        <Logo size={28} />
        <div className="text-[13.5px] text-muted">© 2026 FamilyBank. Educational tool — not a financial service.</div>
      </footer>
    </div>
  );
}

export function LegalSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-serif font-semibold text-[21px]">{title}</h2>
      <div className="text-[15px] leading-[1.7] text-[oklch(38%_0.04_155)] flex flex-col gap-3">{children}</div>
    </section>
  );
}
