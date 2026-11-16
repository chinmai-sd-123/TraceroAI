import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";

import { fontVariables } from "./fonts";
import "./globals.css";

const SITE_URL = "https://www.traceroai.tech";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "TraceroAI: find the step that broke your RAG pipeline",
    template: "%s | TraceroAI",
  },
  description:
    "Open-source failure diagnosis for RAG pipelines. TraceroAI checks every answer, names the step that failed, shows the evidence, and says whether an LLM judge or an estimate decided. Self-hosted, Apache-2.0.",
  keywords: [
    "RAG failure diagnosis",
    "RAG observability",
    "RAG evaluation",
    "LLM evaluation",
    "RAG debugging",
    "LLMOps",
    "retrieval augmented generation",
    "LLM-as-judge",
    "groundedness evaluation",
    "RAG tracing",
    "self-healing RAG",
    "AI observability",
    "TraceroAI",
  ],
  authors: [{ name: "TraceroAI" }],
  creator: "TraceroAI",
  // The preview image comes from app/opengraph-image.tsx.
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    siteName: "TraceroAI",
    title: "TraceroAI: find the step that broke your RAG pipeline",
    description:
      "Open-source failure diagnosis for RAG pipelines. Every answer gets one diagnosis tied to a step, with the evidence, and says whether an LLM judge or an estimate made it.",
  },
  twitter: {
    card: "summary_large_image",
    title: "TraceroAI: find the step that broke your RAG pipeline",
    description: "Open-source failure diagnosis for RAG pipelines, self-hosted with Docker Compose.",
  },
  verification: {
    google: "AE23jg8KjzUiTGdL2J1rXNCubATMZVbo4o5hDlyb4t8",
  },
  alternates: {
    canonical: SITE_URL,
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-scroll-behavior="smooth"
      className={`${fontVariables} h-full`}
    >
      <body className="min-h-full antialiased">
        {children}
        {/* Only on the hosted site. A self-hosted copy sends nothing anywhere. */}
        {process.env.VERCEL && <Analytics />}
      </body>
    </html>
  );
}
