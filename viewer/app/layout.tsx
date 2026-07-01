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
  // Favicons + iOS home-screen icon — same Deliverome brand mark
  // we use in the Shell, so a browser tab / bookmark shows the
  // glyph that visitors associate with the parent property. Matches
  // deliverome-internal:site/app/layout.tsx's icons block exactly so
  // the two sites share their tab-strip glyph.
  icons: {
    icon: "/assets/internalization_logo.svg",
    shortcut: "/assets/internalization_logo.svg",
    apple: "/assets/internalization_logo.svg",
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
    // `summary` (not summary_large_image): we ship no OG image, and a
    // large-image card with no image unfurls as a blank/broken box. The
    // compact card shows title + description cleanly. Switch back to
    // summary_large_image only if a 1200×630 og:image is added to openGraph.
    card: "summary",
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
  // `data-scroll-behavior="smooth"` opts this root into Next 16's
  // route-transition scroll handling that *expects* CSS
  // `scroll-behavior: smooth` on <html>. Without it Next logs a
  // dev-mode warning recommending the attribute when smooth scrolling
  // is detected (used by the gene-page AnchorNav and the in-page
  // "skip to main content" link). See
  // https://nextjs.org/docs/messages/missing-data-scroll-behavior
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body className={`${manrope.variable} ${playfair.variable}`}>{children}</body>
    </html>
  );
}
