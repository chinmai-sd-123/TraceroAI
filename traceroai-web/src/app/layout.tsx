import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";

import { fontVariables } from "./fonts";
import "./globals.css";

const SITE_URL = "https://www.traceroai.tech";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "TraceroAI: know which stage of your RAG pipeline failed",
    template: "%s | TraceroAI",
  },
  description:
    "Open-source tracing and evaluation for RAG pipelines. TraceroAI checks retrieval, grounding and the answer for every response, names the stage that failed, and says whether an LLM judge or an estimate decided.",
  keywords: [
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
    title: "TraceroAI: know which stage of your RAG pipeline failed",
    description:
      "Open-source tracing and evaluation for RAG. Every answer gets a diagnosis tied to a pipeline stage, and says whether an LLM judge or an estimate made it.",
  },
  twitter: {
    card: "summary_large_image",
    title: "TraceroAI: know which stage of your RAG pipeline failed",
    description: "Open-source tracing and evaluation for RAG pipelines, self-hosted with Docker Compose.",
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
        <Analytics />
      </body>
    </html>
  );
}
