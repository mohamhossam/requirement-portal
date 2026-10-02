import { expect } from "@playwright/test";
import { test } from "./library-fixture";

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

test("owner compares a safe image source before reviewing and publishing", async ({ page }, testInfo) => {
  await page.goto("/documents/library");
  await page.getByLabel("Document title").fill(`Visual source ${crypto.randomUUID()}`);
  await page.getByLabel("Original file", { exact: true }).setInputFiles({
    name: "source.png", mimeType: "image/png",
    buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAPAAAAB4CAIAAABD1OhwAAABWklEQVR4nO3SwQkAIBDAMHX/nc8lBKEkE/TRPTMLKs7vAHjJ0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFJMTQphibF0KQYmhRDk2JoUgxNiqFZJRfu1QPtwwWQrgAAAABJRU5ErkJggg==", "base64"),
  });
  await page.getByRole("button", { name: "Upload for private review" }).click();
  await expect(page.getByRole("heading", { name: "Review extracted passages" })).toBeVisible({ timeout: 30000 });
  await page.getByRole("button", { name: "Compare with original source" }).click();
  const image = page.getByRole("img", { name: /Original source:/ });
  await expect(image).toBeVisible();
  await expect.poll(() => image.evaluate((node: HTMLImageElement) => node.naturalWidth)).toBeGreaterThan(0);
  await page.getByRole("textbox", { name: "Reviewed text", exact: true }).fill("Owner checked the source image; no policy content is asserted.");
  await page.getByLabel("Include in shared publication").check();
  await page.getByLabel("Review summary").fill("Verified original visual and reviewed text.");
  await page.getByRole("button", { name: "Save extraction review" }).click();
  await expect(page.getByRole("button", { name: "Approve saved revision" })).toBeEnabled();
  await page.getByRole("button", { name: "Approve saved revision" }).click();
  await expect(page.getByText("Published and searchable", { exact: true })).toBeVisible({ timeout: 30000 });
  await page.getByRole("button", { name: "Compare with original source" }).click();
  await expect(page.getByRole("img", { name: /Original source:/ })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("source-comparison.png"), fullPage: true });
});
