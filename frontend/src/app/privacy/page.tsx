import { LegalPage, LegalSection } from "@/components/legal-page";

export const metadata = { title: "Privacy Policy — FamilyBank" };

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy" updated="September 3, 2026">
      <LegalSection title="What FamilyBank is">
        <p>
          FamilyBank is a virtual allowance tracker. Parents record the allowance/debt they owe
          their kids, and kids can &quot;invest&quot; that virtual balance in real stocks and
          index funds at real, live market prices. <strong>No real bank account is ever
          connected, no real trade is ever placed, and no real money ever moves.</strong> Every
          balance in the app is a number in our database, not a claim on real assets.
        </p>
      </LegalSection>

      <LegalSection title="Who this policy covers">
        <p>
          FamilyBank accounts are created by a parent or guardian, using Sign in with Google.
          Kids do not sign in or create their own accounts in the current version — every detail
          about a kid (name, virtual balance, virtual holdings) is entered and controlled by the
          parent who created the family account. This policy describes what we collect about
          that parent, and what the parent chooses to store about their kids.
        </p>
      </LegalSection>

      <LegalSection title="What we collect">
        <ul className="list-disc pl-5 flex flex-col gap-2">
          <li>
            <strong>From Google Sign-In:</strong> your name, email address, and Google account
            identifier. We never see or store your Google password.
          </li>
          <li>
            <strong>What you enter yourself:</strong> your family&apos;s chosen currency, the
            names, avatars, and running balances of the kids you add, and every add/deduct/buy/
            sell action you record for them.
          </li>
          <li>
            <strong>Standard technical logs:</strong> our hosting providers (see &quot;Who we
            share data with&quot; below) automatically log things like IP address and request
            timestamps for security and reliability, the same way virtually any web service
            does.
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="What we deliberately don't collect">
        <p>
          We never ask for or store bank account numbers, card numbers, or any real payment
          credential — there is nothing to charge, because no real money ever moves through
          FamilyBank.
        </p>
      </LegalSection>

      <LegalSection title="Children's data, specifically">
        <p>
          Because a kid never signs in or interacts with Google/OAuth themselves, we don&apos;t
          knowingly collect personal information directly from a child. Whatever the app knows
          about a kid — name, balance, holdings — was typed in by their parent, who is the one
          with an account, and who can edit or delete it at any time from Settings. If you
          entered a kid&apos;s information and want it fully removed, or want your whole family
          account deleted, contact us (below) and we will delete it.
        </p>
      </LegalSection>

      <LegalSection title="Who we share data with">
        <p>We use a small number of service providers to run FamilyBank, and share only what each one needs to do its job:</p>
        <ul className="list-disc pl-5 flex flex-col gap-2">
          <li><strong>Google</strong> — to authenticate sign-in.</li>
          <li><strong>Neon</strong> — hosts our database (Postgres).</li>
          <li><strong>Vercel</strong> and <strong>Render</strong> — host the website and backend.</li>
          <li>
            <strong>A market-data provider (Yahoo Finance)</strong> — supplies the real stock/
            index prices shown in the app. No personal or family data is ever sent to it; we
            only pull public price data.
          </li>
        </ul>
        <p>We do not sell your data, or your kids&apos; data, to anyone, ever.</p>
      </LegalSection>

      <LegalSection title="How long we keep it">
        <p>
          We keep your family&apos;s data for as long as your account exists. If you ask us to
          delete your account, we delete the underlying family, kid, and transaction records.
        </p>
      </LegalSection>

      <LegalSection title="Security">
        <p>
          We use encrypted connections (HTTPS) throughout, never store your Google password, and
          keep infrastructure secrets out of our source code. No system is perfectly secure, and
          we can&apos;t guarantee absolute security — but we treat your family&apos;s data with
          the same care we&apos;d want for our own.
        </p>
      </LegalSection>

      <LegalSection title="Changes to this policy">
        <p>
          If we make a material change to this policy, we&apos;ll update the date at the top of
          this page. Continued use of FamilyBank after a change means you accept the updated
          policy.
        </p>
      </LegalSection>

      <LegalSection title="Contact">
        <p>
          Questions about this policy, or a request to view/delete your family&apos;s data?
          Email <a href="mailto:amir8985@gmail.com" className="text-emerald underline">amir8985@gmail.com</a>.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
