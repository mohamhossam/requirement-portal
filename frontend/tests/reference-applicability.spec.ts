import { expect } from "@playwright/test";
import { test } from "./library-fixture";
import path from "node:path";

test("published evidence requires an attributed owner decision and stale evidence blocks reuse", async ({ page, request }, testInfo) => {
  const base = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;
  const title = `XGPON policy ${crypto.randomUUID()}`;
  const excerpt = "High-speed bundles require XGPON coverage at the customer address.";
  const uploaded = await request.post(`${base}/library/ingestions`, { multipart: {
    title, idempotency_key: crypto.randomUUID(),
    file: { name: "policy.txt", mimeType: "text/plain", buffer: Buffer.from(excerpt) },
  } });
  expect(uploaded.status()).toBe(202);
  const document = await uploaded.json();
  const sourcePath = `${base}/library/documents/${document.id}`;
  await expect.poll(async () => (await (await request.get(sourcePath)).json()).versions[0].stage).toBe("ready_for_review");
  const extracted = await (await request.get(sourcePath)).json();
  const source = extracted.versions[0];
  const reviewed = await (await request.post(`${sourcePath}/versions/${source.id}/review`, { data: {
    expected_version: extracted.version, explanation: "Synthetic browser fixture reviewed",
    passages: source.blocks.map((b: { id: string; text: string }) => ({ block_id: b.id, text: b.text, included: true, exclusion_reason: "" })),
  } })).json();
  expect((await request.post(`${sourcePath}/versions/${source.id}/approval`, { data: {
    expected_version: reviewed.version, revision_id: reviewed.versions[0].revisions[0].id,
    fingerprint: reviewed.review_fingerprint,
  } })).ok()).toBeTruthy();
  await expect.poll(async () => (await (await request.get(sourcePath)).json()).published_id).toBeTruthy();
  const created = await request.post(`${base}/requirements`, { data: {
    title: "High-speed bundles through BCRM", description: "Allow SMB customers to order high-speed bundles through BCRM.",
    desired_outcome: "Eligible customers can order bundles.",
  } });
  expect(created.ok()).toBeTruthy();
  const requirement = await created.json();
  const current = await (await request.get(`${base}/requirements/${requirement.id}`)).json();
  const generated = await request.post(`${base}/requirements/${requirement.id}/analysis`, { data: { context_token: current.analysis_context_token, force: false } });
  expect(generated.ok(), await generated.text()).toBeTruthy();
  await page.goto(`/requirements/${requirement.id}/clarify`);
  const evidence = page.getByRole("region", { name: "Reference applicability", exact: true }).filter({ hasText: title });
  await expect(evidence).toBeVisible();
  const proposal = evidence.locator("..");
  await expect(proposal.getByRole("button", { name: "Accept as written" })).toBeDisabled();
  await proposal.getByLabel("Applicability rationale").fill("This offer uses the covered XGPON network.");
  await expect(proposal.getByRole("button", { name: "Accept as written" })).toBeEnabled();
  const link = evidence.getByRole("link");
  expect(await link.getAttribute("href")).toContain(`/documents/library/${document.id}?publication=`);
  const [preview] = await Promise.all([page.waitForEvent("popup"), link.click()]);
  await expect(preview.getByRole("region", { name: "Cited published passage" }).getByText(excerpt, { exact: true })).toBeVisible();
  await preview.close();
  if (testInfo.project.name === "responsive-chromium") await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => { if (document.activeElement instanceof HTMLElement) document.activeElement.blur(); window.scrollTo(0, 0); });
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: path.resolve("..", ".impeccable", "review", testInfo.project.name === "chromium" ? "reference-desktop.png" : "reference-mobile.png"), fullPage: true, animations: "disabled" });
  await proposal.getByRole("button", { name: "Accept as written" }).click();
  await expect(page.getByText("Rationale: This offer uses the covered XGPON network.", { exact: false })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Reference applicability — owner decision recorded" })).toBeVisible();
  await page.evaluate(() => { if (document.activeElement instanceof HTMLElement) document.activeElement.blur(); window.scrollTo(0, 0); });
  await page.screenshot({ path: path.resolve("..", ".impeccable", "review", testInfo.project.name === "chromium" ? "reference-decided-desktop.png" : "reference-decided-mobile.png"), fullPage: true, animations: "disabled" });
  const published = await (await request.get(sourcePath)).json();
  expect((await request.post(`${sourcePath}/withdrawal`, { data: { expected_version: published.version, reason: "Superseded policy" } })).ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByRole("alert").filter({ hasText: "Reference evidence changed" })).toBeVisible();
});
