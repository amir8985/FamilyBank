import { LegalPage, LegalSection } from "@/components/legal-page";

export const metadata = { title: "Terms of Service — FamilyBank" };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service" updated="September 3, 2026">
      <LegalSection title="1. What you're agreeing to">
        <p>
          These terms govern your use of FamilyBank. By signing in and creating a family account,
          you agree to them. If you don&apos;t agree, don&apos;t use the app.
        </p>
      </LegalSection>

      <LegalSection title="2. FamilyBank is a virtual educational tool, not a financial service">
        <p>
          FamilyBank tracks allowance/debt a parent owes their kids, and lets kids
          &quot;invest&quot; that virtual balance in real stocks and index funds at real, live
          market prices. <strong>Nothing in the app is a real bank account, brokerage account,
          trade, or investment.</strong> No real money ever moves. Prices shown are for
          illustration and education; past or simulated performance in the app is not
          investment advice and is not indicative of what would happen with real money in a real
          account.
        </p>
      </LegalSection>

      <LegalSection title="3. Who can create an account">
        <p>
          An account must be created by a parent or legal guardian. You&apos;re responsible for
          the accuracy of any information you enter about your kids, and for keeping your Google
          account (which controls access to your FamilyBank family account) secure.
        </p>
      </LegalSection>

      <LegalSection title="4. Acceptable use">
        <p>
          Use FamilyBank only for its intended purpose — tracking allowance and teaching kids
          about investing with virtual money. Don&apos;t attempt to interfere with the service,
          access another family&apos;s data, or use the app in a way that violates any law.
        </p>
      </LegalSection>

      <LegalSection title='5. No warranty, service provided "as is"'>
        <p>
          FamilyBank is provided on an &quot;as is&quot; and &quot;as available&quot; basis, with
          no warranty of any kind — including that it will be uninterrupted, error-free, or that
          market data will always be perfectly current. We rely on third-party hosting and
          market-data providers, and can&apos;t guarantee their availability either.
        </p>
      </LegalSection>

      <LegalSection title="6. Limitation of liability">
        <p>
          To the fullest extent permitted by law, FamilyBank and its operator are not liable for
          any indirect, incidental, or consequential damages arising from your use of the app.
          Because no real money or real trades are ever involved, there is no real financial loss
          that can result from using FamilyBank as intended.
        </p>
      </LegalSection>

      <LegalSection title="7. Your data">
        <p>
          See our <a href="/privacy" className="text-emerald underline">Privacy Policy</a> for
          what we collect and how it&apos;s used. You can request deletion of your family&apos;s
          account and data at any time.
        </p>
      </LegalSection>

      <LegalSection title="8. Termination">
        <p>
          You can stop using FamilyBank and request account deletion at any time. We may suspend
          or terminate access if these terms are violated.
        </p>
      </LegalSection>

      <LegalSection title="9. Governing law">
        <p>
          These terms are governed by the laws of Portugal, without regard to conflict-of-law
          rules. Any dispute arising from your use of FamilyBank will be brought exclusively in
          the courts of Portugal.
        </p>
      </LegalSection>

      <LegalSection title="10. Changes to these terms">
        <p>
          We may update these terms as the app evolves. We&apos;ll update the date at the top of
          this page when we do; continuing to use FamilyBank after a change means you accept the
          update.
        </p>
      </LegalSection>

      <LegalSection title="11. Contact">
        <p>
          Questions about these terms? Email{" "}
          <a href="mailto:amir8985@gmail.com" className="text-emerald underline">
            amir8985@gmail.com
          </a>
          .
        </p>
      </LegalSection>
    </LegalPage>
  );
}
