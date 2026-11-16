import type { ReactNode } from "react";

import { SiteFooter, SiteHeader } from "@/components/site/site-chrome";

import { DocsNav } from "./docs-nav";
import { DocsSearch } from "./docs-search";

// Every docs page: the site header, the docs navigation and search on the left,
// the page itself in the middle (it draws its own "On this page" rail).
export default function DocsLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader current="docs" />
      <div className="mx-auto max-w-[84rem] px-4 sm:px-8 lg:grid lg:grid-cols-[14.5rem_minmax(0,1fr)] lg:gap-10">
        <aside aria-label="Docs navigation" className="pt-6 lg:pt-10">
          <div className="lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto lg:pr-2 lg:pb-10">
            <DocsSearch />
            <DocsNav />
          </div>
        </aside>
        <main className="min-w-0">{children}</main>
      </div>
      <SiteFooter />
    </>
  );
}
