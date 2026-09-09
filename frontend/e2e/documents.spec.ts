import { expect, test } from "@playwright/test";

import { openNav, signIn } from "./helpers";

test("admin can open the Documents page with the upload form", async ({ page }) => {
  await signIn(page);
  await openNav(page);
  await page.getByRole("link", { name: "Documents" }).click();
  await expect(page.getByRole("heading", { name: "Documents", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Upload a PDF" })).toBeVisible();
  await expect(page.getByLabel("Visibility")).toBeVisible();
});
