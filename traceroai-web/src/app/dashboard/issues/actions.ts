"use server";

import { refresh } from "next/cache";
import { cookies } from "next/headers";

import { setIssueResolved } from "@/lib/api";
import { SESSION_COOKIE, isValidSession } from "@/lib/dashboard-auth";

export type IssueActionResult = { ok: true } | { ok: false; error: string };

// Goes through the dashboard's server, which holds the API key, as feedback does.
export async function changeIssue(projectId: string, issueKey: string, resolved: boolean): Promise<IssueActionResult> {
  if (!(await isValidSession((await cookies()).get(SESSION_COOKIE)?.value))) {
    return { ok: false, error: "Your session has expired. Reload the page to sign in." };
  }
  if (!projectId || projectId.length > 100 || !issueKey || issueKey.length > 2000) {
    return { ok: false, error: "Invalid issue." };
  }
  const result = await setIssueResolved(projectId, issueKey, resolved);
  if (!result.ok) {
    return {
      ok: false,
      error:
        result.status === 0
          ? "Couldn't reach the TraceroAI API."
          : result.status === 404
            ? "That issue no longer has any traces."
            : `The API refused (${result.status}).`,
    };
  }
  refresh();
  return { ok: true };
}
