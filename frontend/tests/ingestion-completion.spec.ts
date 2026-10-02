import { expect, test } from "@playwright/test";

const apiUrl = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;

test("Requirement attachments process asynchronously and survive browser reload", async ({ page, request }, testInfo) => {
  const response = await request.post(`${apiUrl}/requirements`, { data: { title: "Async attachment review", description: "Order a bundle" } });
  expect(response.status()).toBe(201);
  const requirement = await response.json();
  await page.goto(`/requirements/${requirement.id}/capture`);
  await page.getByLabel("Attach files", { exact: true }).setInputFiles({ name: "policy.txt", mimeType: "text/plain", buffer: Buffer.from("Coverage must be checked before order submission.") });
  await expect(page.getByText("policy.txt uploaded. Processing continues in the background.")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("checkbox", { name: "Include in analysis", exact: true })).toBeChecked({ timeout: 30000 });
  await expect(page.getByText("policy.txt", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("async-attachment.png"), fullPage: true });
  const ingestions = await (await request.get(`${apiUrl}/requirements/${requirement.id}/document-ingestions`)).json();
  expect(ingestions).toHaveLength(1);
  expect(ingestions[0].attached_document_id).toBeTruthy();
  await page.getByLabel("Attach files", { exact: true }).setInputFiles({
    name: "broken.png", mimeType: "image/png", buffer: Buffer.from("not an image"),
  });
  await expect(page.getByRole("button", { name: "Retry processing broken.png" })).toBeVisible({ timeout: 30000 });
  const retried = page.waitForResponse(response => response.url().includes("/document-ingestions/") && response.url().endsWith("/retry"));
  await page.getByRole("button", { name: "Retry processing broken.png" }).click();
  expect((await retried).ok()).toBeTruthy();
  await expect(page.getByRole("button", { name: "Leave out failed upload broken.png" })).toBeVisible({ timeout: 30000 });
  await page.getByRole("button", { name: "Leave out failed upload broken.png" }).click();
  await expect(page.getByText("Left out of analysis. The failure stays on record.")).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Include in analysis", exact: true })).toBeChecked();
});
