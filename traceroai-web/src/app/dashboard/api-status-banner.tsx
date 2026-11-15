import type { ApiStatus } from "@/lib/api";

import { AlertIcon } from "@/components/icons";

// Shown above every dashboard page when the data below can't be trusted.
// Deliberately doesn't print the API address: it may be an internal host.
const MESSAGES: Record<Exclude<ApiStatus, "ok">, { title: string; body: string }> = {
  unreachable: {
    title: "Can't reach the TraceroAI API",
    body: "Pages may show no data. Check that the API is running and that TRACEROAI_API_URL (or NEXT_PUBLIC_TRACEROAI_API_URL) points at it.",
  },
  unauthorized: {
    title: "The API rejected the dashboard's key",
    body: "Set TRACEROAI_API_KEY on the dashboard to an admin key from TRACEROAI_ADMIN_API_KEYS (or to a project key to show one project).",
  },
  degraded: {
    title: "The API isn't fully available",
    body: "Its database or Redis isn't answering, so data may be missing or out of date. /health/ready on the API says which.",
  },
};

export function ApiStatusBanner({ status }: { status: ApiStatus }) {
  if (status === "ok") return null;
  const message = MESSAGES[status];
  return (
    <div role="alert" className="flex gap-3 border-b border-warn/30 bg-warn-soft px-4 py-3 text-sm sm:px-8">
      <AlertIcon className="mt-0.5 shrink-0 text-warn" />
      <div>
        <p className="font-semibold text-warn">{message.title}</p>
        <p className="mt-0.5 text-ink">{message.body}</p>
      </div>
    </div>
  );
}
