"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_TRACEROAI_API_URL || "http://127.0.0.1:8000";

type Rating = "thumbs_up" | "thumbs_down";

export function FeedbackWidget({ traceId }: { traceId: string }) {
  const router = useRouter();
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
      const response = await fetch(
        `${API_BASE_URL}/v1/traces/${traceId}/feedback`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rating, comment: comment || null }),
        },
      );
      if (!response.ok) {
        throw new Error(`Request failed (${response.status})`);
      }
      setRating(null);
      setComment("");
      router.refresh(); // re-fetch the server component to show the new entry
    } catch {
      setError("Could not submit feedback. Is the API running?");
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