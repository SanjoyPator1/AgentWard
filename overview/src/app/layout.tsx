import type { Metadata } from "next";
import { Playfair_Display, Inter, IBM_Plex_Mono, Caveat } from "next/font/google";
import "./globals.css";

const serif = Playfair_Display({
  variable: "--font-serif",
  subsets: ["latin"],
  weight: ["600", "700", "800", "900"],
});

const sans = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const mono = IBM_Plex_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const hand = Caveat({
  variable: "--font-hand",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

export const metadata: Metadata = {
  title: "AgentWard — Overview",
  description:
    "AgentWard: an AI agent harness for synthetic patients. Synthea-generated FHIR behind an MCP tool layer, graded by code oracles.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${serif.variable} ${sans.variable} ${mono.variable} ${hand.variable} h-full antialiased`}
    >
      <body className="min-h-full h-full overflow-hidden bg-paper text-ink font-sans">
        {children}
      </body>
    </html>
  );
}
