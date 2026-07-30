import { test, expect } from "@playwright/test";

test.describe("Core flows", () => {
  test("should display the runs page", async ({ page }) => {
    await page.goto("/runs");
    await expect(page).toHaveURL(/runs/);
  });

  test("should display the dataset-ingest page", async ({ page }) => {
    await page.goto("/upload");
    await expect(page).toHaveURL(/upload/);
  });

  test("should navigate to files page", async ({ page }) => {
    await page.goto("/files");
    await expect(page).toHaveURL(/files/);
  });

  test("should display the dashboard", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body")).toBeVisible();
  });
});
