import type { Metadata } from "next";
import { Manrope, Playfair_Display } from "next/font/google";
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const playfair = Playfair_Display({
  subsets: ["latin"],
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});

const SITE_URL = "https://surfaceome.deliverome.org";
const SITE_TITLE = "Surfaceome — Deliverome";
const SITE_DESCRIPTION =
  "A working atlas of cell-surface proteins — open accession, evidence-cited, agent-readable.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_TITLE,
    template: `%s | Surfaceome`,
  },
  description: SITE_DESCRIPTION,
  applicationName: "Surfaceome",
  // Favicons + iOS home-screen icon — same provisional Deliverome logo
  // we use as the brand mark in the Shell, so a browser tab / bookmark
  // shows the Deliverome glyph that visitors associate with the parent
  // property. Matches deliverome-internal:site/app/layout.tsx's icons
  // block exactly so the two sites share their tab-strip glyph.
  icons: {
    icon: "/assets/provisional_logo.svg",
    shortcut: "/assets/provisional_logo.svg",
    apple: "/assets/provisional_logo.svg",
  },
  openGraph: {
    type: "website",
    siteName: SITE_TITLE,
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    url: SITE_URL,
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${manrope.variable} ${playfair.variable}`}>{children}</body>
    </html>
  );
}
