import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ContentsRail } from "@/components/site/contents-rail";
import { headingsOf, readSource } from "@/lib/docs-content";
import { DOC_PAGES, docHref, placeOf } from "@/lib/docs-nav";

import { OldAnchorRedirect } from "../old-anchor-redirect";

type Params = { slug?: string[] };

export const dynamicParams = false;

export function generateStaticParams(): Params[] {
  return DOC_PAGES.map((p) => ({ slug: p.slug ? p.slug.split("/") : [] }));
}

function slugOf(params: Params) {
  return (params.slug ?? []).join("/");
}

async function load(slug: string) {
  if (!DOC_PAGES.some((p) => p.slug === slug)) return null;
  const mdx = await import(`@/content/docs/${slug || "index"}.mdx`);
  return { Content: mdx.default as React.ComponentType, meta: (mdx.meta ?? {}) as { description?: string } };
}

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const slug = slugOf(await params);
  const loaded = await load(slug);
  const { page } = placeOf(slug);
  if (!loaded || !page) return {};
  return {
    title: slug ? `${page.title} · Docs` : "Documentation",
    description: loaded.meta.description,
  };
}

export default async function DocPage({ params }: { params: Promise<Params> }) {
  const slug = slugOf(await params);
  const loaded = await load(slug);
  const { page, previous, next } = placeOf(slug);
  if (!loaded || !page) notFound();
  const headings = headingsOf(await readSource(slug)).filter((h) => h.depth === 2);

  return (
    <div className="xl:grid xl:grid-cols-[minmax(0,1fr)_12.5rem] xl:gap-10">
      <article className="min-w-0 max-w-[48rem] pt-8 pb-16 lg:pt-10">
        {!slug && <OldAnchorRedirect />}
        <h1 className="text-[2.25rem] leading-tight font-bold tracking-[-0.025em] text-balance">{page.title}</h1>
        {loaded.meta.description && (
          <p className="mt-3 max-w-[62ch] text-lg leading-8 text-ink-muted">{loaded.meta.description}</p>
        )}
        <div className="mt-2">
          <loaded.Content />
        </div>

        <nav aria-label="Previous and next" className="mt-16 grid gap-3 border-t border-line pt-6 sm:grid-cols-2">
          {previous ? (
            <Link href={docHref(previous.slug)} className="rounded border border-line px-4 py-3 hover:border-accent">
              <span className="block text-xs text-ink-muted">Previous</span>
              <span className="font-medium text-accent">{previous.title}</span>
            </Link>
          ) : (
            <span />
          )}
          {next && (
            <Link href={docHref(next.slug)} className="rounded border border-line px-4 py-3 text-right hover:border-accent">
              <span className="block text-xs text-ink-muted">Next</span>
              <span className="font-medium text-accent">{next.title}</span>
            </Link>
          )}
        </nav>
      </article>

      {headings.length > 1 && (
        <aside aria-label="On this page" className="hidden xl:block">
          <div className="sticky top-20 pt-10">
            <ContentsRail items={headings.map((h) => ({ id: h.id, label: h.text }))} label="On this page" />
          </div>
        </aside>
      )}
    </div>
  );
}
