import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const SITE_URL = "https://www.traceroai.tech";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "TraceroAI — RAG Observability, Evaluation & Self-Healing",
    template: "%s | TraceroAI",
  },
  description:
    "Debug RAG failures before they reach users. TraceroAI traces, evaluates, and diagnoses retrieval-augmented generation pipelines with an LLM-as-judge and a self-healing recovery agent.",
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
  openGraph: {
    type: "website",
    locale: "en_IN",
    url: SITE_URL,
    siteName: "TraceroAI",
    title: "TraceroAI — Debug RAG Failures Before They Reach Users",
    description:
      "Trace, evaluate, and diagnose RAG pipelines. Two-tier evaluation (embedding + LLM judge), self-healing recovery agent, and an experiment harness for A/B testing retrieval configs.",
    images: [
      {
        url: "/dashboard.png",
        width: 1200,
        height: 630,
        alt: "TraceroAI reliability dashboard showing healthy rate, failure mix, and latency metrics",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "TraceroAI — RAG Observability & Self-Healing",
    description:
      "Debug RAG failures before they reach users. LLM-as-judge evaluation, self-healing recovery, and experiment harness.",
    images: ["/dashboard.png"],
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
      className={`${geistSans.variable} ${geistMono.variable} h-full`}
    >
      <body className="min-h-full antialiased">
        {children}
        <Analytics />
      </body>
    </html>
  );
}
