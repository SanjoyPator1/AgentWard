import type { Metadata } from "next";
import { Geist_Mono, Inter } from "next/font/google";
import { ToolDetailProvider } from "@/components/chat/tool-detail-drawer";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono-geist",
});

export const metadata: Metadata = {
  title: "AgentWard - F1 Care Gap Viewer",
  description: "Watch the F1 care-gap agent investigate patients live, and browse its worklist.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className={`${inter.variable} ${geistMono.variable} h-full font-sans antialiased`}>
        <ToolDetailProvider>{children}</ToolDetailProvider>
      </body>
    </html>
  );
}
