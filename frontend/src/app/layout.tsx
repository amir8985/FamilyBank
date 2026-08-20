import type { Metadata, Viewport } from "next";
import { Source_Serif_4, Work_Sans } from "next/font/google";
import { SessionProvider } from "next-auth/react";
import { RegisterServiceWorker } from "@/components/register-sw";
import "./globals.css";

const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const workSans = Work_Sans({
  variable: "--font-work-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "FamilyBank",
  description:
    "Track the allowance you owe your kids, and let them invest it in real stocks and indices — virtual money, real prices.",
  manifest: "/manifest.webmanifest",
  icons: [{ rel: "icon", url: "/icon.svg", type: "image/svg+xml" }],
};

export const viewport: Viewport = {
  themeColor: "oklch(25% 0.06 155)",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${sourceSerif.variable} ${workSans.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-cream-canvas">
        <SessionProvider>{children}</SessionProvider>
        <RegisterServiceWorker />
      </body>
    </html>
  );
}
