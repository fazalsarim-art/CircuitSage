import { expect, test } from "@playwright/test";

import { signIn } from "./helpers";

test("sign in lands on the app shell", async ({ page }) => {
  await signIn(page);
  await expect(page.getByRole("heading", { name: /Ask a debugging question/i })).toBeVisible();
  await expect(page.getByText("liveadmin@example.com")).toBeVisible();
});

test("signing out returns to the sign-in page", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in to CircuitSage" })).toBeVisible();
});
