import { expect, test } from "@playwright/test";

import { signIn } from "./helpers";

test("asking with an empty corpus shows guidance to upload documents", async ({ page }) => {
  await signIn(page);
  await page.getByRole("textbox", { name: "Question" }).fill("Why does the SPI status register stay busy?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/No indexed documents yet/i)).toBeVisible();
});
