// Optional shared-password gate for the dashboard.
//
// Set TRACEROAI_DASHBOARD_PASSWORD and the dashboard asks for it before showing
// anything; leave it unset (local development, a public demo) and the dashboard
// is open. This is a stopgap until real user accounts exist: everyone with the
// password sees whatever TRACEROAI_API_KEY can read.
//
// The session cookie holds an HMAC of the password, not the password, and a new
// password invalidates every existing session.

export const SESSION_COOKIE = "traceroai_dashboard";
export const SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;

export function dashboardPassword(): string | undefined {
  return process.env.TRACEROAI_DASHBOARD_PASSWORD || undefined;
}

export async function sessionToken(password: string): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(password),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode("traceroai-dashboard-session-v1"),
  );
  return Array.from(new Uint8Array(signature), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

/** Compare two strings without returning early on the first difference. */
export function constantTimeEqual(a: string, b: string): boolean {
  let diff = a.length ^ b.length;
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  }
  return diff === 0;
}

/** True when no password is configured, or the cookie matches the current one. */
export async function isValidSession(cookieValue: string | undefined): Promise<boolean> {
  const password = dashboardPassword();
  if (!password) return true;
  if (!cookieValue) return false;
  return constantTimeEqual(cookieValue, await sessionToken(password));
}

/** Only same-site dashboard paths are accepted as a post-login destination. */
export function safeNextPath(next: string | undefined | null): string {
  if (next && next.startsWith("/dashboard") && !next.startsWith("//")) {
    return next;
  }
  return "/dashboard";
}
