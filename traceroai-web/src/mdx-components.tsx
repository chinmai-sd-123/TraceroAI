import type { MDXComponents } from "mdx/types";
import Link from "next/link";
import { isValidElement, type ComponentProps, type ReactElement, type ReactNode } from "react";

import { CodeBlock, CodeTabs } from "@/components/site/code-tabs";
import { DiagnosisTable, Note, TryPlayground } from "@/components/site/doc-blocks";

// How the docs' MDX renders. Required by @next/mdx in the App Router.

function Heading({ as: Tag, id, children }: { as: "h2" | "h3"; id?: string; children?: ReactNode }) {
  const size = Tag === "h2" ? "mt-12 text-[1.375rem] tracking-[-0.015em]" : "mt-8 text-[1.0625rem]";
  return (
    <Tag id={id} className={`group scroll-mt-24 font-semibold text-ink ${size}`}>
      {children}
      {id && (
        <a
          href={`#${id}`}
          aria-label="Link to this section"
          className="ml-2 font-normal text-ink-faint opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
        >
          #
        </a>
      )}
    </Tag>
  );
}

function CodeFromFence({ children }: { children?: ReactNode }) {
  // Fenced code arrives as <pre><code className="language-x">text</code></pre>.
  const code = isValidElement(children) ? (children as ReactElement<{ className?: string; children?: ReactNode }>) : null;
  const language = code?.props.className?.replace(/^language-/, "");
  const text = typeof code?.props.children === "string" ? code.props.children : String(code?.props.children ?? "");
  return (
    <div className="mt-5">
      <CodeBlock code={text.replace(/\n$/, "")} language={language} />
    </div>
  );
}

function DocLink({ href = "", children, ...rest }: ComponentProps<"a">) {
  const className = "text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent";
  if (href.startsWith("/") || href.startsWith("#")) {
    return (
      <Link href={href} className={className}>
        {children}
      </Link>
    );
  }
  return (
    <a href={href} className={className} {...rest}>
      {children}
    </a>
  );
}

export function useMDXComponents(components: MDXComponents): MDXComponents {
  return {
    h2: (props) => <Heading as="h2" {...props} />,
    h3: (props) => <Heading as="h3" {...props} />,
    p: (props) => <p className="mt-4 max-w-[70ch] leading-7 text-ink-muted" {...props} />,
    a: DocLink,
    strong: (props) => <strong className="font-semibold text-ink" {...props} />,
    ul: (props) => <ul className="mt-4 max-w-[70ch] list-disc space-y-1.5 pl-5 leading-7 text-ink-muted marker:text-ink-faint" {...props} />,
    ol: (props) => <ol className="mt-4 max-w-[70ch] list-decimal space-y-1.5 pl-5 leading-7 text-ink-muted marker:text-ink-faint" {...props} />,
    li: (props) => <li className="pl-1" {...props} />,
    code: (props) => (
      <code className="rounded-[3px] bg-sunken px-1 py-px font-dash-mono text-[0.8125rem] text-ink" {...props} />
    ),
    pre: CodeFromFence,
    table: (props) => (
      <div className="mt-5 overflow-x-auto rounded border border-line">
        <table className="w-full min-w-[32rem] border-collapse text-sm" {...props} />
      </div>
    ),
    thead: (props) => <thead className="bg-sunken text-left text-xs text-ink-muted" {...props} />,
    th: (props) => <th scope="col" className="border-b border-line-strong px-4 py-2 font-medium" {...props} />,
    td: (props) => <td className="border-t border-line px-4 py-2.5 align-top leading-6 text-ink-muted" {...props} />,
    blockquote: ({ children }) => <Note>{children}</Note>,
    hr: () => <hr className="mt-10 border-line" />,
    CodeTabs,
    Note,
    DiagnosisTable,
    Playground: TryPlayground,
    ...components,
  };
}
