"use client";

import { useState } from "react";

import type { FeedbackRating as Rating } from "@/lib/api";

import { ThumbDownIcon, ThumbUpIcon } from "@/components/icons";
import { submitFeedback } from "./actions";

export function FeedbackWidget({ traceId }: { traceId: string }) {
  const [rating, setRating] = useState<Rating | null>(null);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function submit() {
    if (!rating) {
      setError("Choose Helpful or Not helpful first.");
      return;
    }
    setSubmitting(true);
    setError(null);
    setSaved(false);
    try {
      const result = await submitFeedback(traceId, rating, comment);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setRating(null);
      setComment(""); // the action refreshes the page, which lists the new entry
      setSaved(true);
    } catch {
      setError("Couldn't save the feedback. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-3">
      <fieldset>
        <legend className="sr-only">Rating</legend>
        <div className="flex gap-2">
          <RatingButton active={rating === "thumbs_up"} onClick={() => setRating("thumbs_up")}>
            <ThumbUpIcon className={rating === "thumbs_up" ? "text-pass" : "text-ink-muted"} /> Helpful
          </RatingButton>
          <RatingButton active={rating === "thumbs_down"} onClick={() => setRating("thumbs_down")}>
            <ThumbDownIcon className="text-ink-muted" /> Not helpful
          </RatingButton>
        </div>
      </fieldset>

      <div>
        <label htmlFor="feedback-comment" className="mb-1 block text-sm text-ink-muted">
          Note (optional)
        </label>
        <textarea
          id="feedback-comment"
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="What was wrong, or what should it have said?"
          rows={3}
          maxLength={2000}
          className="w-full rounded border border-line-strong bg-surface px-3 py-2 text-sm placeholder:text-ink-faint focus:outline-2 focus:outline-accent"
        />
      </div>

      {error && (
        <p role="alert" className="text-sm text-warn">
          {error}
        </p>
      )}
      {saved && !error && (
        <p role="status" className="text-sm text-pass">
          Feedback saved.
        </p>
      )}

      <button
        type="button"
        onClick={submit}
        disabled={submitting}
        className="rounded bg-accent px-3.5 py-1.5 text-sm font-medium text-white hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? "Saving…" : "Save feedback"}
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
      aria-pressed={active}
      className={`inline-flex items-center gap-2 rounded border px-3 py-1.5 text-sm ${
        active
          ? "border-accent bg-accent-soft font-medium text-accent"
          : "border-line-strong bg-surface text-ink hover:bg-sunken"
      }`}
    >
      {children}
    </button>
  );
}
