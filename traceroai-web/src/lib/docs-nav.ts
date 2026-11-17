// The docs' table of contents. Each page is src/content/docs/<slug>.mdx (the
// introduction is index.mdx); this order is the sidebar's and prev/next's.

export type DocPage = { slug: string; title: string };
export type DocGroup = { name: string; pages: DocPage[] };

export const DOCS_NAV: DocGroup[] = [
  {
    name: "Getting started",
    pages: [
      { slug: "", title: "Introduction" },
      { slug: "quickstart", title: "Quickstart" },
      { slug: "first-diagnosis", title: "Read your first diagnosis" },
    ],
  },
  {
    name: "Concepts",
    pages: [
      { slug: "concepts/traces", title: "Traces" },
      { slug: "concepts/diagnoses", title: "Diagnoses" },
      { slug: "concepts/estimates-and-verdicts", title: "Estimates and judge verdicts" },
      { slug: "concepts/accuracy", title: "Accuracy" },
      { slug: "concepts/issues", title: "Issues" },
      { slug: "concepts/projects-and-keys", title: "Projects and keys" },
    ],
  },
  {
    name: "Instrument",
    pages: [
      { slug: "instrument/python-sdk", title: "Python SDK" },
      { slug: "instrument/async", title: "Async code" },
      { slug: "instrument/opentelemetry", title: "OpenTelemetry" },
      { slug: "instrument/chunks", title: "Retriever output and chunks" },
      { slug: "instrument/delivery", title: "Delivery and failures" },
    ],
  },
  {
    name: "Diagnose and fix",
    pages: [
      { slug: "fix/investigate", title: "Investigate failures" },
      { slug: "fix/recovery-agent", title: "Recovery agent" },
      { slug: "fix/experiments", title: "Experiments" },
    ],
  },
  {
    name: "Reference",
    pages: [
      { slug: "reference/sdk", title: "SDK reference" },
      { slug: "reference/http-api", title: "HTTP API" },
      { slug: "reference/configuration", title: "Configuration" },
      { slug: "reference/trace-data", title: "What a trace contains" },
    ],
  },
  {
    name: "Self-host",
    pages: [
      { slug: "self-host/docker-compose", title: "Docker Compose" },
      { slug: "self-host/production", title: "Production checklist" },
      { slug: "self-host/upgrading", title: "Upgrading" },
      { slug: "self-host/troubleshooting", title: "Troubleshooting" },
    ],
  },
  {
    name: "Project",
    pages: [
      { slug: "try-it", title: "Try it" },
    ],
  },
];

export const DOC_PAGES: DocPage[] = DOCS_NAV.flatMap((g) => g.pages);

export function docHref(slug: string) {
  return slug ? `/docs/${slug}` : "/docs";
}

/** The page's group, and the pages before and after it in reading order. */
export function placeOf(slug: string) {
  const index = DOC_PAGES.findIndex((p) => p.slug === slug);
  const group = DOCS_NAV.find((g) => g.pages.some((p) => p.slug === slug));
  return {
    page: DOC_PAGES[index],
    group: group?.name,
    previous: index > 0 ? DOC_PAGES[index - 1] : undefined,
    next: index >= 0 && index < DOC_PAGES.length - 1 ? DOC_PAGES[index + 1] : undefined,
  };
}

// Where the sections of the old single-page docs went, for /docs#<section> links.
export const OLD_ANCHORS: Record<string, string> = {
  install: "quickstart",
  "self-host": "self-host/docker-compose",
  trace: "instrument/python-sdk",
  reference: "reference/sdk",
  diagnosis: "concepts/diagnoses",
  recovery: "fix/recovery-agent",
  experiments: "fix/experiments",
  auth: "concepts/projects-and-keys",
  config: "reference/configuration",
  "http-api": "reference/http-api",
  troubleshooting: "self-host/troubleshooting",
  try: "try-it",
};
