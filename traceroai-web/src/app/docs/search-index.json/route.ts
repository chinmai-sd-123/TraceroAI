import { searchIndex } from "@/lib/docs-content";

// Every docs section's text, built once at build time, for the docs search.
export const dynamic = "force-static";

export async function GET() {
  return Response.json(await searchIndex());
}
