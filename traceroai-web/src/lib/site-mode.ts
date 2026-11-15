// TraceroAI is self-hosted: the dashboard reads your own API. A deployment of
// just the public pages (landing and docs, say on Vercel) sets no API address,
// so the dashboard and the docs playground explain how to run the stack
// instead of failing to reach an API that isn't there. In development the
// default local address is assumed.

export function apiConfigured(): boolean {
  return (
    Boolean(process.env.TRACEROAI_API_URL || process.env.NEXT_PUBLIC_TRACEROAI_API_URL) ||
    process.env.NODE_ENV !== "production"
  );
}

/** Whether browser code has an API to call (the docs playground). */
export function publicApiConfigured(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_TRACEROAI_API_URL) || process.env.NODE_ENV !== "production";
}
