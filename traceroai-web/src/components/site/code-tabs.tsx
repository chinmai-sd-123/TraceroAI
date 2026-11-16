"use client";

import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { CopyButton } from "@/components/copy-button";

export type CodeTab = { label: string; code: string; language?: string };

// Light-touch highlighting: comments, strings and keywords only, which is
// enough to read the shape of a snippet without a highlighting library.
const PY_KEYWORDS = new Set([
  "from", "import", "with", "as", "def", "return", "for", "in", "if", "else", "None", "True", "False", "lambda", "print",
]);

/** Highlight python or shell code; anything else (json, yaml, env, text) stays plain. */
export function highlight(code: string, language: string | undefined): ReactNode[] {
  if (language !== "python" && language !== "bash" && language !== "sh" && language !== "shell") return [code];
  if (language !== "python") language = "bash";
  const pattern =
    language === "bash"
      ? /(#.*$)|("[^"\n]*"|'[^'\n]*')|(\b(?:pip|docker|git|cd|export|compose|python)\b)/gm
      : /(#.*$)|("""[\s\S]*?"""|"[^"\n]*"|'[^'\n]*')|(\b[A-Za-z_]+\b)/gm;
  const out: ReactNode[] = [];
  let last = 0;
  for (const match of code.matchAll(pattern)) {
    const [text, comment, string, word] = match;
    if (word && language !== "bash" && !PY_KEYWORDS.has(word)) continue;
    const index = match.index ?? 0;
    if (index > last) out.push(code.slice(last, index));
    const color = comment ? "text-[#8a96a8]" : string ? "text-[#9fd5b5]" : "text-[#a9c2e8]";
    out.push(
      <span key={index} className={color}>
        {text}
      </span>,
    );
    last = index + text.length;
  }
  if (last < code.length) out.push(code.slice(last));
  return out;
}

/** Code in tabs, each with a copy button. Arrow keys move between tabs. */
export function CodeTabs({ tabs, caption }: { tabs: CodeTab[]; caption?: string }) {
  const [active, setActive] = useState(0);
  const id = useId();
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const tab = tabs[active];

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const next = (active + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    setActive(next);
    refs.current[next]?.focus();
  }

  return (
    <figure className="overflow-hidden rounded border border-[#2a3646] bg-[#14202e] text-[#dfe4ea]">
      <div className="flex items-center justify-between gap-3 border-b border-white/10 pr-2.5 pl-1">
        {tabs.length > 1 ? (
          <div role="tablist" aria-label={caption ?? "Code examples"} onKeyDown={onKey} className="flex overflow-x-auto">
            {tabs.map((t, i) => (
              <button
                key={t.label}
                ref={(el) => {
                  refs.current[i] = el;
                }}
                type="button"
                role="tab"
                id={`${id}-tab-${i}`}
                aria-selected={i === active}
                aria-controls={`${id}-panel`}
                tabIndex={i === active ? 0 : -1}
                onClick={() => setActive(i)}
                className={`-mb-px border-b-2 px-3 py-2.5 text-xs font-medium whitespace-nowrap focus-visible:outline-offset-[-2px] focus-visible:outline-[#a9c2e8] ${
                  i === active ? "border-[#a9c2e8] text-white" : "border-transparent text-[#a3adbd] hover:text-white"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        ) : (
          <span className="px-3 py-2.5 text-xs text-[#a3adbd]">{caption ?? tab.label}</span>
        )}
        <CopyButton text={tab.code} tone="dark" />
      </div>
      <pre
        id={`${id}-panel`}
        role={tabs.length > 1 ? "tabpanel" : undefined}
        aria-labelledby={tabs.length > 1 ? `${id}-tab-${active}` : undefined}
        tabIndex={0}
        className="overflow-x-auto px-5 py-4 font-dash-mono text-[0.8125rem] leading-6 focus-visible:outline-offset-[-2px] focus-visible:outline-[#a9c2e8]"
      >
        <code>{highlight(tab.code, tab.language ?? "python")}</code>
      </pre>
    </figure>
  );
}

const LANGUAGE_NAMES: Record<string, string> = {
  python: "Python",
  bash: "Terminal",
  sh: "Terminal",
  shell: "Terminal",
  json: "JSON",
  yaml: "YAML",
  env: ".env",
  sql: "SQL",
  ts: "TypeScript",
  text: "Text",
};

/** One code block with a copy button (fenced code in the docs). */
export function CodeBlock({ code, language, caption }: { code: string; language?: string; caption?: string }) {
  const label = caption ?? LANGUAGE_NAMES[language ?? ""] ?? "Code";
  return <CodeTabs tabs={[{ label, code, language }]} caption={label} />;
}
