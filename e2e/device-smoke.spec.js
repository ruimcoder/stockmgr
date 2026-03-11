const { test, expect } = require("@playwright/test");

test("cross-device smoke flow", async ({ page, request, browserName }) => {
  const email = `device.${browserName}.${Date.now()}@example.com`;

  await page.goto("/register");
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="display_name"]').fill("Device QA");
  await page.getByRole("button", { name: /Submit registration/i }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: /Inventory/i })).toBeVisible();

  await page.goto("/items/new");
  await expect(page.locator("#start-camera-scan")).toBeVisible();
  await expect(page.locator("#barcode-scan-status")).toBeVisible();

  await page.goto("/device-check");
  await expect(page.getByRole("heading", { name: /Device Compatibility Check/i })).toBeVisible();
  await expect(page.locator("#cap-secure-context")).not.toHaveText("-");

  const manifest = await request.get("/manifest.webmanifest");
  expect(manifest.ok()).toBeTruthy();
  const serviceWorker = await request.get("/service-worker.js");
  expect(serviceWorker.ok()).toBeTruthy();
});
