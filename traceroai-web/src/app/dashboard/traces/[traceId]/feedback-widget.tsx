"use client";

import { useState } from "react";

import type { FeedbackRating as Rating } from "@/lib/api";

import { submitFeedback } from "./actions";

export function FeedbackWidget({ traceId }: { traceId: string }) {
  const [rating, setRating] = useState<Rating | null>(null);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!rating) {
      setError("Pick 👍 or 👎 first.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await submitFeedback(traceId, rating, comment);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setRating(null);
      setComment(""); // the action refreshes the page, which shows the new entry
    } catch {
      setError("Couldn't submit feedback. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <RatingButton
          active={rating === "thumbs_up"}
          onClick={() => setRating("thumbs_up")}
        >
          👍 Helpful
        </RatingButton>
        <RatingButton
          active={rating === "thumbs_down"}
          onClick={() => setRating("thumbs_down")}
        >
          👎 Not helpful
        </RatingButton>
      </div>

      <textarea
        value={comment}
        onChange={(event) => setComment(event.target.value)}
        placeholder="Optional comment…"
        rows={2}
        className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none"
      />

      {error && <p className="text-xs text-red-400">{error}</p>}

      <button
        type="button"
        onClick={submit}
        disabled={submitting}
        className="rounded-md bg-cyan-300 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-200 disabled:opacity-50"
      >
        {submitting ? "Submitting…" : "Submit feedback"}
      </button>
    </div>
  );
}

function RatingButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border px-3 py-2 text-sm font-medium transition ${
        active
          ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200"
          : "border-zinc-800 bg-zinc-900/60 text-zinc-300 hover:border-zinc-700"
      }`}
    >
      {children}
    </button>
  );
}