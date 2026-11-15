"use client";

import { useEffect, useRef, useState } from "react";

import { CheckIcon, CopyIcon } from "@/components/icons";

/** Copies `text`; the icon turns into a check and the label reads "Copied"
 * for two seconds. */
export function CopyButton({
  text,
  label = "Copy",
  tone = "light",
}: {
  text: string;
  label?: string;
  tone?: "light" | "dark"; // dark: on a code block
}) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      setState("failed"); // no clipboard permission, or not a secure context
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setState("idle"), 2000);
  }

  const copied = state === "copied";
  return (
    <button
      type="button"
      onClick={copy}
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-1 text-xs font-medium ${
        tone === "dark"
          ? "border-white/20 bg-transparent text-[#dfe4ea] hover:bg-white/10"
          : "border-line-strong bg-surface text-ink hover:bg-sunken"
      }`}
    >
      <span className="relative size-4">
        <CopyIcon
          className={`absolute inset-0 transition-[opacity,scale] duration-200 ease-out ${copied ? "scale-50 opacity-0" : "opacity-100"}`}
        />
        <CheckIcon
          className={`absolute inset-0 transition-[opacity,scale] duration-200 ease-out ${tone === "dark" ? "text-[#8fd3a8]" : "text-pass"} ${copied ? "opacity-100" : "scale-50 opacity-0"}`}
        />
      </span>
      <span aria-live="polite">{copied ? "Copied" : state === "failed" ? "Couldn't copy" : label}</span>
    </button>
  );
}
