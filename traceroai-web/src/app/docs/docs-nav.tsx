"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { DOCS_NAV, docHref } from "@/lib/docs-nav";

/** The docs' table of contents. On phones it folds into a menu. */
export function DocsNav() {
  const pathname = usePathname().replace(/\/$/, "") || "/docs";
  const current = DOCS_NAV.flatMap((g) => g.pages).find((p) => docHref(p.slug) === pathname);

  const list = (
    <nav aria-label="Documentation" className="space-y-6 text-sm">
      {DOCS_NAV.map((group) => (
        <div key={group.name}>
          <p className="px-2 pb-1.5 font-semibold text-ink">{group.name}</p>
          <ul className="space-y-px border-l border-line">
            {group.pages.map((page) => {
              const href = docHref(page.slug);
              const active = href === pathname;
              return (
                <li key={page.slug}>
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={`-ml-px block border-l-2 py-1 pr-2 pl-3 leading-5 ${
                      active
                        ? "border-accent font-medium text-accent"
                        : "border-transparent text-ink-muted hover:border-line-strong hover:text-ink"
                    }`}
                  >
                    {page.title}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );

  return (
    <>
      <div className="mt-6 hidden lg:block">{list}</div>
      <details className="group mt-4 rounded border border-line-strong lg:hidden">
        <summary className="flex cursor-pointer list-none items-center justify-between px-3 py-2 text-sm font-medium">
          <span>
            <span className="text-ink-muted">Docs: </span>
            {current?.title ?? "Contents"}
          </span>
          <span aria-hidden="true" className="text-ink-muted transition-transform group-open:rotate-180">
            ▾
          </span>
        </summary>
        <div className="border-t border-line px-1 py-4">{list}</div>
      </details>
    </>
  );
}
