import { test, expect } from "@playwright/test";
async function login(page, character) {
  await page.goto("/");
  await page.getByLabel("Your local access token").fill(character.repeat(24));
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.getByText("Keep the context moving.")).toBeVisible();
}
test("creates an incident, transfers ownership only after recipient acceptance", async ({
  browser,
}) => {
  const owner = await browser.newContext();
  const recipient = await browser.newContext();
  const a = await owner.newPage(),
    s = await recipient.newPage();
  await login(a, "a");
  await login(s, "s");
  await a.getByRole("button", { name: "Open incident" }).click();
  await a
    .getByLabel("Title", { exact: true })
    .fill("Checkout latency after release");
  await a.getByLabel("Service", { exact: true }).fill("checkout-api");
  await a
    .getByLabel("Initial evidence")
    .fill("p95 increased after canary rollout. Baseline remains healthy.");
  await a.getByRole("button", { name: "Create incident" }).click();
  await expect(a.locator("#detail")).toContainText(
    "Checkout latency after release",
  );
  await a.getByLabel("Next action").selectOption("handoff");
  await a.getByLabel("Destination").selectOption("Sam");
  await a
    .getByLabel("Context / evidence")
    .fill("Inspect the payment-provider timeout. Rollback remains available.");
  await a.getByRole("button", { name: "Record update" }).click();
  await expect(a.locator(".notice")).toContainText("Alex remains responsible");
  await s.getByRole("button", { name: "Refresh" }).click();
  await s.locator(".incident").first().click();
  await s.getByLabel("Next action").selectOption("accept");
  await s
    .getByLabel("Context / evidence")
    .fill("Reviewed trace and canary evidence; taking ownership.");
  await s.getByRole("button", { name: "Record update" }).click();
  await expect(s.locator(".meta")).toContainText("Owner: Sam");
  await expect(s.locator(".timeline li")).toHaveCount(3);
  await s.screenshot({ path: "docs/preview.png", fullPage: true });
  await owner.close();
  await recipient.close();
});
test("stale concurrent edit preserves the draft and exposes the latest timeline", async ({
  browser,
}) => {
  const context = await browser.newContext();
  const a = await context.newPage();
  await login(a, "a");
  await a.request.post("/api/incidents", {
    headers: { Authorization: "Bearer " + "a".repeat(24) },
    data: {
      title: "Concurrent edit scenario",
      service: "test",
      severity: "SEV3",
      note: "Synthetic browser test",
    },
  });
  await a.getByRole("button", { name: "Refresh" }).click();
  await a.locator(".incident").first().click();
  const b = await context.newPage();
  await login(b, "a");
  await b.locator(".incident").first().click();
  await a
    .getByLabel("Context / evidence")
    .fill("Fresh evidence from first tab");
  await a.getByRole("button", { name: "Record update" }).click();
  await expect(a.getByRole("status")).toContainText("Update recorded");
  await b.getByLabel("Context / evidence").fill("Draft from stale tab");
  await b.getByRole("button", { name: "Record update" }).click();
  await expect(b.getByRole("status")).toContainText("Someone updated");
  await expect(b.getByLabel("Context / evidence")).toHaveValue(
    "Draft from stale tab",
  );
  await expect(b.locator(".timeline")).toContainText(
    "Fresh evidence from first tab",
  );
  await context.close();
});
test("viewer is read-only and mobile layout fits", async ({ page }) => {
  await page.request.post("/api/incidents", {
    headers: { Authorization: "Bearer " + "a".repeat(24) },
    data: {
      title: "Viewer access scenario",
      service: "test",
      severity: "SEV3",
      note: "Synthetic browser test",
    },
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, "v");
  await expect(
    page.getByRole("button", { name: "Open incident" }),
  ).toBeHidden();
  await page.locator(".incident").first().click();
  await expect(page.getByText("You have read-only access.")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
});
