"use server";

import { refresh } from "next/cache";
import { cookies } from "next/headers";

import { type FeedbackRating, postFeedback } from "@/lib/api";
import { SESSION_COOKIE, isValidSession } from "@/lib/dashboard-auth";

const MAX_COMMENT_LENGTH = 2000;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export type FeedbackResult = { ok: true } | { ok: false; error: string };

// Feedback goes through the dashboard's server, which holds the API key, so the
// browser never needs one.
export async function submitFeedback(
  traceId: string,
  rating: FeedbackRating,
  comment: string,
): Promise<FeedbackResult> {
  if (!(await isValidSession((await cookies()).get(SESSION_COOKIE)?.value))) {
    return { ok: false, error: "Your session has expired. Reload the page to sign in." };
  }
  if (!UUID_PATTERN.test(traceId) || (rating !== "thumbs_up" && rating !== "thumbs_down")) {
    return { ok: false, error: "Invalid feedback." };
  }
  const trimmed = comment.trim();
  if (trimmed.length > MAX_COMMENT_LENGTH) {
    return { ok: false, error: `Keep the comment under ${MAX_COMMENT_LENGTH} characters.` };
  }

  const result = await postFeedback(traceId, rating, trimmed || null);
  if (!result.ok) {
    return {
      ok: false,
      error:
        result.status === 429
          ? "Too much feedback at once. Wait a minute and try again."
          : result.status === 0
            ? "Couldn't reach the TraceroAI API."
            : `The API rejected the feedback (${result.status}).`,
    };
  }

  refresh();
  return { ok: true };
}
