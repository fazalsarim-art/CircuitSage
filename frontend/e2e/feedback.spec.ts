import { expect, test } from "@playwright/test";

import { openNav, signIn } from "./helpers";

test("admin can open the Feedback review page", async ({ page }) => {
  await signIn(page);
  await openNav(page);
  await page.getByRole("link", { name: "Feedback" }).click();
  await expect(page.getByRole("heading", { name: "Feedback", exact: true })).toBeVisible();
  await expect(page.getByText(/Nothing enters the benchmark automatically/i)).toBeVisible();
  await expect(page.getByLabel("Filter by status")).toBeVisible();
});

test("feedback status filter offers the review states", async ({ page }) => {
  await signIn(page);
  await openNav(page);
  await page.getByRole("link", { name: "Feedback" }).click();
  const filter = page.getByLabel("Filter by status");
  await expect(filter.getByRole("option", { name: "promoted_to_draft" })).toBeAttached();
  await filter.selectOption("resolved");
  await expect(filter).toHaveValue("resolved");
});
