import { expect, type Page } from "@playwright/test";

export async function signIn(page: Page): Promise<void> {
  await page.goto("/");
  await page.getByLabel("Email").fill("liveadmin@example.com");
  await page.getByLabel("Password").fill("adminpassword123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

/** Open the navigation drawer if it is collapsed (mobile widths). */
export async function openNav(page: Page): Promise<void> {
  const toggle = page.getByRole("button", { name: "Toggle navigation" });
  if (await toggle.isVisible()) {
    await toggle.click();
  }
}
