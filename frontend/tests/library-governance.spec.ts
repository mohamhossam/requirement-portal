import { expect } from "@playwright/test";
import { test } from "./library-fixture";
import path from "node:path";

test("owner inspects dependencies, withdraws evidence and hands over private control", async ({ page, request }, testInfo) => {
  const base = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;
  const title = `XGPON ownership ${crypto.randomUUID()}`;
  const upload = await request.post(`${base}/library/ingestions`, { multipart: {
    title, idempotency_key: crypto.randomUUID(),
    file: { name: "policy.txt", mimeType: "text/plain", buffer: Buffer.from("High-speed bundles require XGPON coverage at the customer address.") },
  } });
  expect(upload.ok()).toBeTruthy();
  const document = await upload.json();
  const endpoint = `${base}/library/documents/${document.id}`;
  await expect.poll(async () => (await (await request.get(endpoint)).json()).versions[0].stage).toBe("ready_for_review");
  await page.goto(`/documents/library/${document.id}`);
  await page.getByLabel("Review summary").fill("Synthetic policy reviewed");
  await page.getByRole("button", { name: "Save extraction review" }).click();
  await expect(page.getByRole("button", { name: "Approve saved revision" })).toBeEnabled();
  await page.getByRole("button", { name: "Approve saved revision" }).click();
  await expect(page.getByText("Published and searchable", { exact: true })).toBeVisible();
  const created = await request.post(`${base}/requirements`, { data: {
    title: "High-speed bundles through BCRM", description: "Allow SMB customers to order high-speed bundles through BCRM.", desired_outcome: "Eligible customers can order bundles.",
  } });
  const requirement = await created.json();
  const current = await (await request.get(`${base}/requirements/${requirement.id}`)).json();
  const generated = await request.post(`${base}/requirements/${requirement.id}/analysis`, { data: { context_token: current.analysis_context_token, force: false } });
  expect(generated.ok(), await generated.text()).toBeTruthy();
  await page.getByRole("button", { name: "View dependencies" }).click();
  await expect(page.getByRole("link", { name: "High-speed bundles through BCRM", exact: true })).toBeVisible();
  await expect(page.getByText("Current analysis · Round 1 · Pending decision")).toBeVisible();
  await page.getByLabel("Why is this evidence no longer safe to use?").fill("Retired synthetic policy");
  await page.getByRole("button", { name: "Withdraw from search now" }).click();
  await expect(page.getByText(/Cited publication was withdrawn or replaced/)).toBeVisible();
  await page.getByRole("button", { name: "Manage ownership" }).click();
  await page.getByLabel("New document owner").selectOption("fake-reviewer");
  await page.getByLabel("Reason for ownership transfer").fill("Ravi is the new policy custodian.");
  const transfer = page.getByRole("button", { name: "Transfer ownership", exact: true });
  await expect(transfer).toBeDisabled();
  await page.getByRole("checkbox", { name: "I understand that I will lose private access and management of this document." }).check();
  await expect(transfer).toBeEnabled();
  await page.getByLabel("Find a workspace user").fill("Ravi");
  await expect(transfer).toBeDisabled();
  await expect(page.getByRole("checkbox", { name: "I understand that I will lose private access and management of this document." })).not.toBeChecked();
  await page.getByLabel("New document owner").selectOption("fake-reviewer");
  await page.getByRole("checkbox", { name: "I understand that I will lose private access and management of this document." }).check();
  await expect(transfer).toBeEnabled();
  if (testInfo.project.name === "responsive-chromium") await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => { if (document.activeElement instanceof HTMLElement) document.activeElement.blur(); window.scrollTo(0, 0); });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const suffix = testInfo.project.name === "chromium" ? "desktop" : "mobile";
  await page.screenshot({ path: path.resolve("../.impeccable/review", `governance-${suffix}.png`), fullPage: true, animations: "disabled" });
  await page.locator("section").filter({ has: page.getByRole("heading", { name: "Document ownership", exact: true }) }).screenshot({ path: path.resolve("../.impeccable/review", `ownership-${suffix}.png`) });
  await transfer.click();
  await expect(page.getByText("Ownership transferred to Ravi Reviewer. Your private access has ended.")).toBeVisible();
  await expect(page.getByRole("link", { name: title, exact: true })).toHaveCount(0);
  expect((await request.get(endpoint)).status()).toBe(404);
  await page.getByLabel("Development persona").selectOption("fake-reviewer");
  await page.goto(`/documents/library/${document.id}`);
  await expect(page.getByText(/Owner: Ravi Reviewer/)).toBeVisible();
  await page.getByRole("button", { name: "Manage ownership" }).click();
  await expect(page.getByText("Ravi is the new policy custodian.")).toBeVisible();
  await page.getByRole("button", { name: "View dependencies" }).click();
  await expect(page.getByText("No recorded references on this page in Requirements you can access.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Download original for comparison" })).toBeEnabled();
});
