import { test, expect } from "@playwright/test";

/**
 * Covers what's safely automatable without a real Google account:
 * the public landing page, and that every authenticated route
 * correctly bounces an unauthenticated visitor back to it. Google's
 * own login screen can't be scripted here (see backend/tests/test_api_auth.py
 * for how the post-login flow is tested instead), so the authenticated
 * screens (home, onboarding, buy) aren't covered by this suite — they're
 * covered by the backend's API-level end-to-end tests.
 */

test("landing page renders the hero and brand", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /bank your kids will actually want to open/i })).toBeVisible();
  await expect(page.getByText("FamilyBank").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Get started" })).toBeVisible();
});

test("landing page has no console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  await page.goto("/");
  await page.waitForLoadState("networkidle").catch(() => {});
  expect(errors).toEqual([]);
});

for (const path of ["/home", "/home/settings", "/onboarding"]) {
  test(`${path} redirects an unauthenticated visitor to the landing page`, async ({ page }) => {
    await page.goto(path);
    await expect(page).toHaveURL("/");
  });
}
