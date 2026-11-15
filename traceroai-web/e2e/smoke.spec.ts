import { expect, test } from "@playwright/test";

test("the landing page renders", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText("pip install traceroai").first()).toBeVisible();
});

test("the docs render with their contents", async ({ page }) => {
  await page.goto("/docs");
  await expect(page.getByRole("heading", { name: "Run the stack" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Troubleshooting" })).toBeVisible();
});

test("the dashboard says the API is down instead of showing empty data", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByText("Can't reach the TraceroAI API")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Dashboard" })).toBeVisible();
});
