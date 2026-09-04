import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { Logo } from "@/components/ui/logo";
import { SignInButton } from "@/components/sign-in-button";

export default async function LandingPage() {
  const session = await auth();
  if (session?.backendToken) redirect("/home");

  return (
    <div className="flex flex-col min-h-screen bg-cream text-emerald-dark">
      <nav className="sticky top-0 z-10 flex items-center justify-between px-6 md:px-16 py-[18px] md:py-[22px] bg-cream/92 backdrop-blur-sm border-b border-border-hairline">
        <Logo size={38} />
        <div className="hidden md:flex items-center gap-9 text-[15px] font-medium">
          <a href="#how" className="hover:text-brass">How it works</a>
          <a href="#safety" className="hover:text-brass">Safety</a>
          <a href="#faq" className="hover:text-brass">FAQ</a>
        </div>
        <SignInButton className="bg-emerald text-cream px-[22px] py-[11px] rounded-lg text-[14px] font-semibold cursor-pointer">
          Get started
        </SignInButton>
      </nav>

      <header className="flex flex-col md:flex-row items-center gap-10 md:gap-16 px-6 md:px-16 py-14 md:py-24 max-w-[1280px] mx-auto w-full box-border">
        <div className="flex-1 flex flex-col gap-6 min-w-0">
          <div className="inline-flex items-center gap-2 bg-tint-emerald text-emerald px-3.5 py-[7px] rounded-full text-[12.5px] font-semibold w-fit">
            Virtual money · Real market prices
          </div>
          <h1 className="font-serif font-semibold text-[36px] md:text-[52px] leading-[1.08] tracking-[-0.01em] m-0">
            A bank your kids will actually want to open.
          </h1>
          <p className="text-[18px] leading-[1.6] text-[oklch(38%_0.04_155)] max-w-[480px] m-0">
            Track the allowance you owe each kid, and let them invest it in real stocks and index
            funds at real prices — with money that always stays play money. No broker, no risk, all
            the lesson.
          </p>
          <div className="flex gap-3.5 mt-2 flex-wrap">
            <SignInButton className="bg-emerald text-cream px-7 py-[15px] rounded-[9px] text-[15px] font-semibold cursor-pointer">
              Create your family
            </SignInButton>
            <a
              href="#how"
              className="bg-transparent border-[1.5px] border-[oklch(80%_0.02_155)] text-emerald-dark px-7 py-[15px] rounded-[9px] text-[15px] font-semibold"
            >
              See how it works
            </a>
          </div>
        </div>

        <div className="flex-1 flex justify-center min-w-0 w-full">
          <div className="w-full max-w-[340px] flex flex-col gap-4">
            <div className="bg-card rounded-2xl p-[22px] shadow-[0_20px_50px_rgba(0,0,0,.1)] border border-border-hairline">
              <div className="text-[13px] font-semibold text-muted mb-3.5">You owe</div>
              <div className="flex flex-col gap-3.5">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2.5">
                    <div className="w-[34px] h-[34px] rounded-full bg-avatar-amber flex items-center justify-center text-[13px] font-semibold text-emerald">
                      M
                    </div>
                    <div className="text-[14.5px] font-medium">Maya</div>
                  </div>
                  <div className="font-serif font-semibold text-[18px] text-emerald">
                    <span className="font-sans">₪</span>128.50
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2.5">
                    <div className="w-[34px] h-[34px] rounded-full bg-avatar-teal flex items-center justify-center text-[13px] font-semibold text-emerald">
                      N
                    </div>
                    <div className="text-[14.5px] font-medium">Noam</div>
                  </div>
                  <div className="font-serif font-semibold text-[18px] text-emerald">
                    <span className="font-sans">₪</span>64.00
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-emerald rounded-2xl p-[22px] shadow-[0_20px_50px_rgba(0,0,0,.14)]">
              <div className="flex justify-between items-baseline mb-3">
                <div className="text-[13px] font-semibold text-[oklch(85%_0.02_155)]">Maya&apos;s portfolio</div>
                <div className="text-[12px] font-semibold text-[oklch(72%_0.11_75)]">+4.2%</div>
              </div>
              <div className="font-serif font-semibold text-[26px] text-white mb-3.5">
                <span className="font-sans">₪</span>212.30
              </div>
              <div className="flex items-end gap-[5px] h-11">
                <div className="w-full rounded-sm bg-[oklch(40%_0.06_155)]" style={{ height: "40%" }} />
                <div className="w-full rounded-sm bg-[oklch(40%_0.06_155)]" style={{ height: "55%" }} />
                <div className="w-full rounded-sm bg-[oklch(40%_0.06_155)]" style={{ height: "48%" }} />
                <div className="w-full rounded-sm bg-brass" style={{ height: "70%" }} />
                <div className="w-full rounded-sm bg-brass" style={{ height: "85%" }} />
              </div>
            </div>
          </div>
        </div>
      </header>

      <section className="px-6 md:px-16 py-5 border-y border-border-hairline bg-[oklch(94%_0.015_100)]">
        <div className="max-w-[1280px] mx-auto flex justify-center gap-8 md:gap-14 flex-wrap text-[14px] font-semibold text-[oklch(35%_0.04_155)]">
          {["No real broker", "No real money moves", "Real, live market prices", "Parent stays in control"].map(
            (claim) => (
              <div key={claim} className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-brass" />
                {claim}
              </div>
            )
          )}
        </div>
      </section>

      <section id="how" className="px-6 md:px-16 py-16 md:py-24 max-w-[1280px] mx-auto w-full box-border">
        <div className="text-center mb-14">
          <h2 className="font-serif font-semibold text-[30px] md:text-[36px] mb-3">How FamilyBank works</h2>
          <p className="text-[16px] text-muted-strong">Three simple pieces, one family ledger.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <FeatureCard
            title="Track what you owe"
            body="Add allowance, log chores paid, or dock money for the week — one running balance per kid, with full history."
            icon={
              <div className="flex items-end gap-[3px] h-5">
                <div className="w-[5px] rounded-[1px] bg-emerald" style={{ height: 10 }} />
                <div className="w-[5px] rounded-[1px] bg-emerald" style={{ height: 16 }} />
                <div className="w-[5px] rounded-[1px] bg-emerald" style={{ height: 20 }} />
              </div>
            }
          />
          <FeatureCard
            title="Invest it, virtually"
            body="Kids put their balance into real stocks and index funds at real, live prices — and watch it move like the real market, with none of the real risk."
            icon={<div className="w-5 h-5 rounded-full border-[3px] border-emerald" />}
          />
          <FeatureCard
            title="Parents stay in charge"
            body="Only a parent can add money to a kid's balance. Everything else — buying, selling, browsing — is safe to hand over."
            icon={
              <div
                className="w-[22px] h-6 bg-emerald"
                style={{ clipPath: "polygon(0 0,100% 0,100% 62%,50% 100%,0 62%)" }}
              />
            }
          />
        </div>
      </section>

      <section id="safety" className="px-6 md:px-16 py-16 md:py-20 bg-emerald">
        <div className="max-w-[900px] mx-auto text-center flex flex-col items-center gap-[18px]">
          <div className="w-12 h-12 rounded-full bg-brass/18 border-2 border-brass flex items-center justify-center">
            <div className="w-4 h-4 rounded-full border-[3px] border-brass" />
          </div>
          <h2 className="font-serif font-semibold text-[26px] md:text-[30px] text-white m-0">
            This is a lesson, not a brokerage.
          </h2>
          <p className="text-[16px] leading-[1.7] text-[oklch(85%_0.02_155)] max-w-[620px] m-0">
            Every price your kid sees is real. Every dollar behind it is not. FamilyBank never
            touches a bank account, never places a real trade, and never moves real money — it&apos;s
            a family ledger with a real-market lesson built in.
          </p>
        </div>
      </section>

      <footer className="px-6 md:px-16 py-10 flex items-center justify-between border-t border-border-hairline flex-wrap gap-4">
        <Logo size={28} />
        <div className="flex items-center gap-5 text-[13.5px]">
          <a href="/privacy" className="text-muted hover:text-brass">Privacy Policy</a>
          <a href="/terms" className="text-muted hover:text-brass">Terms of Service</a>
          <div className="text-muted">© 2026 FamilyBank. Educational tool — not a financial service.</div>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({ title, body, icon }: { title: string; body: string; icon: React.ReactNode }) {
  return (
    <div className="bg-card rounded-2xl p-8 border border-border-hairline">
      <div className="w-11 h-11 rounded-[10px] bg-tint-emerald flex items-center justify-center mb-5">{icon}</div>
      <h3 className="font-serif font-semibold text-[19px] mb-2.5">{title}</h3>
      <p className="text-[14.5px] leading-[1.6] text-muted-strong m-0">{body}</p>
    </div>
  );
}
