"use server";

import { cookies } from "next/headers";
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

export async function login(_previous: LoginState, formData: FormData): Promise<LoginState> {
  const password = dashboardPassword();
  const next = safeNextPath(formData.get("next")?.toString());
  if (!password) {
    redirect(next);
  }

  const attempt = formData.get("password")?.toString() ?? "";
  if (!constantTimeEqual(attempt, password)) {
    return { error: "Wrong password." };
  }

  (await cookies()).set(SESSION_COOKIE, await sessionToken(password), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  });
  redirect(next);
}
