// Server only: reads the MDX sources from disk.
import { readFile } from "node:fs/promises";
import path from "node:path";

import GithubSlugger from "github-slugger";

import { DOC_PAGES, type DocPage } from "./docs-nav";

// Server-side reading of the docs' MDX sources: the headings for "On this page"
// and the text for search. Slugs come from github-slugger, the same library
// rehype-slug uses for the rendered headings, so the ids match.

const CONTENT_DIR = path.join(process.cwd(), "src", "content", "docs");

export function sourcePath(slug: string) {
  return path.join(CONTENT_DIR, `${slug || "index"}.mdx`);
}

export type Heading = { id: string; text: string; depth: 2 | 3 };

/** Markdown text of a source, without code blocks, imports, exports and JSX lines. */
function proseLines(source: string): string[] {
  const lines: string[] = [];
  let inFence = false;
  for (const line of source.split(/\r?\n/)) {
    if (line.trimStart().startsWith("```")) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;
    if (/^(import|export)\s/.test(line) || /^\s*<\/?[A-Z]/.test(line)) continue;
    lines.push(line);
  }
  return lines;
}

/** Inline markdown to plain text. */
function plain(text: string) {
  return text
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1") // links: keep the words
    .replace(/[`*]/g, "") // code and emphasis marks (underscores stay: names like TRACEROAI_API_URL)
    .replace(/\s*\|\s*/g, " ") // table cell borders
    .replace(/^-{3,}$/, "")
    .trim();
}

export function headingsOf(source: string): Heading[] {
  const slugger = new GithubSlugger();
  const headings: Heading[] = [];
  for (const line of proseLines(source)) {
    const match = /^(#{2,3})\s+(.+?)\s*#*$/.exec(line);
    if (!match) continue;
    const text = plain(match[2]);
    headings.push({ id: slugger.slug(text), text, depth: match[1].length as 2 | 3 });
  }
  return headings;
}

export async function readSource(slug: string): Promise<string> {
  return readFile(sourcePath(slug), "utf-8");
}

export type SearchEntry = {
  slug: string;
  page: string; // page title
  heading: string | null; // section heading, null for the page's opening text
  anchor: string | null;
  text: string;
};

/** One entry per section of every page, for the docs search. */
export async function searchIndex(): Promise<SearchEntry[]> {
  const entries: SearchEntry[] = [];
  for (const page of DOC_PAGES) {
    entries.push(...sectionsOf(page, await readSource(page.slug)));
  }
  return entries;
}

function sectionsOf(page: DocPage, source: string): SearchEntry[] {
  const slugger = new GithubSlugger();
  const entries: SearchEntry[] = [];
  let current: SearchEntry = { slug: page.slug, page: page.title, heading: null, anchor: null, text: "" };
  for (const line of proseLines(source)) {
    const match = /^(#{1,3})\s+(.+?)\s*#*$/.exec(line);
    if (match && match[1].length >= 2) {
      entries.push(current);
      const text = plain(match[2]);
      current = { slug: page.slug, page: page.title, heading: text, anchor: slugger.slug(text), text: "" };
    } else if (!match) {
      current.text += ` ${plain(line.replace(/^[-*>|]\s*/, ""))}`;
    }
  }
  entries.push(current);
  return entries.map((e) => ({ ...e, text: e.text.replace(/\s+/g, " ").trim().slice(0, 1200) }));
}
