"use server";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";

import {
  SESSION_COOKIE,
  SESSION_MAX_AGE_SECONDS,
  constantTimeEqual,
  dashboardPassword,
  safeNextPath,
  sessionToken,
} from "@/lib/dashboard-auth";

export type LoginState = { error: string | null };

// Wrong passwords are limited per client address: MAX_FAILURES within the
// window, then refused until it passes. The count lives in this server
// process, so with several instances (serverless) each keeps its own; the
// fixed delay on every failure slows guessing either way.
const MAX_FAILURES = 10;
const WINDOW_MS = 15 * 60 * 1000;
const FAILURE_DELAY_MS = 600;
const failures = new Map<string, { count: number; resetAt: number }>();

async function clientAddress(): Promise<string> {
  const h = await headers();
  // Set by the hosting proxy (Vercel, Render). Only the first entry is the client.
  return h.get("x-forwarded-for")?.split(",")[0]?.trim() || h.get("x-real-ip") || "unknown";
}

function blocked(address: string, now: number): boolean {
  const entry = failures.get(address);
  if (!entry || entry.resetAt <= now) return false;
  return entry.count >= MAX_FAILURES;
}

function recordFailure(address: string, now: number) {
  const entry = failures.get(address);
  if (!entry || entry.resetAt <= now) {
    failures.set(address, { count: 1, resetAt: now + WINDOW_MS });
  } else {
    entry.count += 1;
  }
  // Keep the map from growing without bound.
  if (failures.size > 5000) {
    for (const [key, value] of failures) if (value.resetAt <= now) failures.delete(key);
  }
}

export async function login(_previous: LoginState, formData: FormData): Promise<LoginState> {
  const password = dashboardPassword();
  const next = safeNextPath(formData.get("next")?.toString());
  if (!password) {
    redirect(next);
  }

  const address = await clientAddress();
  const now = Date.now();
  if (blocked(address, now)) {
    return { error: "Too many wrong passwords. Try again in 15 minutes." };
  }

  const attempt = formData.get("password")?.toString() ?? "";
  if (!constantTimeEqual(attempt, password)) {
    recordFailure(address, now);
    await new Promise((resolve) => setTimeout(resolve, FAILURE_DELAY_MS));
    return { error: "Wrong password." };
  }

  failures.delete(address);
  (await cookies()).set(SESSION_COOKIE, await sessionToken(password), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  });
  redirect(next);
}

/** End the session: clear the cookie and go back to the sign-in page. */
export async function logout(): Promise<void> {
  (await cookies()).delete(SESSION_COOKIE);
  redirect(dashboardPassword() ? "/login" : "/dashboard");
}
