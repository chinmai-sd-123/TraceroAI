import { expect, test } from "@playwright/test";

test("the landing page renders, opens its case and its menus", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Find the step that broke." })).toBeVisible();
  await expect(page.getByText("pip install traceroai").first()).toBeVisible();

  // The hero's case file reaches its verdict.
  await expect(page.getByRole("article", { name: "Case file for trace 5f7bf901" }).getByText("Unsupported claim")).toBeVisible({
    timeout: 10_000,
  });

  // Header panels open by click and close with Escape.
  await page.getByRole("button", { name: "Product" }).click();
  await expect(page.getByRole("link", { name: /Measured accuracy/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("link", { name: /Measured accuracy/ })).toBeHidden();
});

test("the docs render, navigate and search", async ({ page }) => {
  await page.goto("/docs");
  await expect(page.getByRole("heading", { level: 1, name: "Introduction" })).toBeVisible();
  await page.getByRole("navigation", { name: "Documentation" }).getByRole("link", { name: "Quickstart" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "1. Run the stack" })).toBeVisible();

  // Search is a static index: it works with no API behind the site.
  await page.getByRole("button", { name: "Search the docs" }).click();
  await page.getByRole("textbox", { name: "Search the docs" }).fill("retention");
  await expect(page.getByRole("option").first()).toBeVisible();

  // Links to the old single-page docs land on the new pages.
  await page.goto("/docs#troubleshooting");
  await expect(page).toHaveURL(/\/docs\/self-host\/troubleshooting$/);
});

test("the dashboard says the API is down instead of showing empty data", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByText("Can't reach the TraceroAI API")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Dashboard" })).toBeVisible();
});
