import { expect } from "@playwright/test";
import { test } from "./library-fixture";
import path from "node:path";

test("reuse, document dependencies, replacement and explicit impact review preserve history", async ({ page, request }, testInfo) => {
  test.setTimeout(120_000);
  const base = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;
  const title = `Lineage policy ${crypto.randomUUID()}`;
  const excerpt = "High-speed bundles require XGPON coverage at the customer address.";
  const upload = await request.post(`${base}/library/ingestions`, { multipart: {
    title, idempotency_key: crypto.randomUUID(),
    file: { name: "policy.txt", mimeType: "text/plain", buffer: Buffer.from(excerpt) },
  } });
  expect(upload.status()).toBe(202);
  const document = await upload.json();
  const sourcePath = `${base}/library/documents/${document.id}`;
  await expect.poll(async () => (await (await request.get(sourcePath)).json()).versions[0].stage).toBe("ready_for_review");
  await page.goto(`/documents/library/${document.id}`);
  await page.getByLabel("Review summary").fill("Synthetic policy verified");
  await page.getByRole("button", { name: "Save extraction review" }).click();
  await expect(page.getByRole("button", { name: "Approve saved revision" })).toBeEnabled();
  await page.getByRole("button", { name: "Approve saved revision" }).click();
  await expect(page.getByText("Published and searchable", { exact: true })).toBeVisible();
  const published = await (await request.get(sourcePath)).json();
  const created = await request.post(`${base}/requirements`, { data: {
    title, description: "Order high-speed bundles through BCRM.", desired_outcome: "Eligible customers can order bundles.",
  } });
  const requirement = await created.json();
  const current = await (await request.get(`${base}/requirements/${requirement.id}`)).json();
  const analysisResponse = await request.post(`${base}/requirements/${requirement.id}/analysis`, { data: { context_token: current.analysis_context_token, force: false } });
  expect(analysisResponse.ok(), await analysisResponse.text()).toBeTruthy();
  const analysis = await analysisResponse.json();
  const question = analysis.questions[0];
  const suggestionPath = `${base}/requirements/${requirement.id}/analysis/questions/${question.id}/answer-suggestions`;
  await expect.poll(async () => (await (await request.get(suggestionPath)).json())?.suggestions?.some((s: { reference_evidence: { document_id: string }[] }) => s.reference_evidence.some(c => c.document_id === document.id)), { timeout: 30000 }).toBeTruthy();
  await page.goto(`/requirements/${requirement.id}/clarify`);
  const questionRow = page.locator("details").filter({ has: page.locator("summary", { hasText: question.subject }) }).first();
  await questionRow.locator("summary").first().click();
  await questionRow.getByRole("button").filter({ hasText: "Published reference · applicability unconfirmed" }).first().click();
  await page.getByRole("button", { name: "Send 1 answer and re-analyse", exact: true }).click();
  await expect.poll(async () => (await (await request.get(`${base}/requirements/${requirement.id}/analysis`)).json()).round_number, { timeout: 30000 }).toBe(2);
  await page.reload();
  await page.getByRole("button", { name: "Review source impact", exact: true }).click();
  const impact = page.getByRole("region", { name: "Source lineage and change impact" });
  await expect(impact.getByRole("article", { name: "clarification source dependency" })).toBeVisible();
  await expect(impact.getByText(/Indirect dependency/).first()).toBeVisible();
  await page.goto(`/documents/library/${document.id}`);
  await page.getByRole("button", { name: "Review source impact", exact: true }).click();
  await expect(page.getByRole("article", { name: "clarification source dependency" })).toBeVisible();
  // Replacing a publication is a separate immutable upload and review.
  const replacement = await request.post(`${base}/library/ingestions`, { multipart: {
    title, document_id: document.id, expected_version: String(published.version), idempotency_key: crypto.randomUUID(),
    file: { name: "policy-v2.txt", mimeType: "text/plain", buffer: Buffer.from("Updated policy: verify XGPON coverage and review the new rollout scope.") },
  } });
  expect(replacement.ok(), await replacement.text()).toBeTruthy();
  await expect.poll(async () => (await (await request.get(sourcePath)).json()).versions.at(-1).stage).toBe("ready_for_review");
  await page.reload();
  await page.getByLabel("Review summary").fill("Replacement policy verified");
  await page.getByRole("button", { name: "Save extraction review" }).click();
  await expect(page.getByRole("button", { name: "Approve saved revision" })).toBeEnabled();
  await page.getByRole("button", { name: "Approve saved revision" }).click();
  await expect.poll(async () => (await (await request.get(sourcePath)).json()).published_id).not.toBe(published.published_id);
  await page.goto(`/requirements/${requirement.id}/clarify`);
  await page.getByRole("button", { name: "Review source impact", exact: true }).click();
  const answer = impact.getByRole("article", { name: "clarification source dependency" });
  await expect(answer.getByText("Publication changed — review required")).toBeVisible();
  await answer.getByText("Exact source and lineage", { exact: true }).click();
  await expect(answer.locator("blockquote")).toHaveText(excerpt);
  await answer.getByRole("combobox", { name: "Impact decision", exact: true }).selectOption("retain_historical");
  await answer.getByLabel("Reason for impact decision").fill("This answer applies to the earlier rollout and retains the reviewed version.");
  await answer.getByRole("button", { name: "Record impact decision" }).click();
  await expect(answer.getByText("Historical evidence — review recorded")).toBeVisible();
  await answer.getByText("Impact review history", { exact: true }).click();
  await expect(answer.getByText("This answer applies to the earlier rollout and retains the reviewed version.")).toBeVisible();
  const latest = await (await request.get(sourcePath)).json();
  expect((await request.post(`${sourcePath}/withdrawal`, { data: { expected_version: latest.version, reason: "Replacement also retired" } })).ok()).toBeTruthy();
  await impact.getByRole("button", { name: "Refresh source impact" }).click();
  await expect(answer.getByText("Publication changed — review required")).toBeVisible();
  // Publication state changed again; prior review remains visible but is no longer sufficient.
  await answer.getByText("Impact review history", { exact: true }).click();
  await expect(answer.getByText("This answer applies to the earlier rollout and retains the reviewed version.")).toBeVisible();
  expect((await request.get(`${base}/library/requirements/${requirement.id}/source-impact`, { headers: { "X-Fake-Actor-Id": "fake-observer" } })).status()).toBe(403);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.resolve("../.impeccable/review", `lineage-${testInfo.project.name}.png`), fullPage: true, animations: "disabled" });
  if (testInfo.project.name === "responsive-chromium") {
    await page.setViewportSize({ width: 390, height: 844 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: path.resolve("../.impeccable/review/lineage-mobile.png"), fullPage: true, animations: "disabled" });
  }
});
