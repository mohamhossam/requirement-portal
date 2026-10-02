import { expect } from "@playwright/test";
import { test } from "./library-fixture";
import path from "node:path";

test("unified search and reference answers retain exact published citations", async ({ page, request }, testInfo) => {
  if (testInfo.project.name === "responsive-chromium") await page.setViewportSize({ width: 390, height: 900 });
  const base = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;
  const title = `Grounding policy ${crypto.randomUUID()}`;
  const excerpt = `Orders for ${title} require XGPON coverage before activation.`;
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
    title, description: "Allow SMB customers to order high-speed bundles through BCRM.",
    desired_outcome: "Eligible customers can order bundles.",
  } });
  expect(created.ok()).toBeTruthy();
  const requirement = await created.json();
  const current = await (await request.get(`${base}/requirements/${requirement.id}`)).json();
  const generated = await request.post(`${base}/requirements/${requirement.id}/analysis`, { data: { context_token: current.analysis_context_token, force: false } });
  expect(generated.ok(), await generated.text()).toBeTruthy();
  await page.goto("/documents/library");
  await page.getByRole("combobox", { name: "Search in", exact: true }).selectOption("all");
  await page.getByLabel("Search text").fill(title);
  const searchResponse = page.waitForResponse(response =>
    response.url().endsWith("/knowledge/search/unified") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Search knowledge", exact: true }).click();
  const searched = await searchResponse;
  expect(searched.ok(), await searched.text()).toBe(true);
  const results = page.getByRole("region", { name: "Unified search results" });
  await expect(results.getByText("Published document", { exact: true }).first()).toBeVisible();
  await expect(results.getByText("Requirement evidence", { exact: true }).first()).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.resolve("../.impeccable/review", `grounding-search-${testInfo.project.name}.png`), fullPage: true });
  const analysis = await generated.json();
  const question = analysis.questions[0];
  const suggestionPath = `${base}/requirements/${requirement.id}/analysis/questions/${question.id}/answer-suggestions`;
  await expect.poll(async () => (await (await request.get(suggestionPath)).json())?.suggestions?.some((s: { reference_evidence: unknown[] }) => s.reference_evidence.length > 0), { timeout: 30000 }).toBeTruthy();
  await page.goto(`/requirements/${requirement.id}/clarify`);
  const questionRow = page.locator("details").filter({ has: page.locator("summary", { hasText: question.subject }) }).first();
  await questionRow.locator("summary").first().click();
  const suggestion = questionRow.getByRole("button").filter({ hasText: "Published reference · applicability unconfirmed" }).first();
  await expect(suggestion).toBeVisible();
  await suggestion.click();
  const citation = questionRow.getByRole("link").filter({ hasText: title }).first();
  await expect(citation).toHaveAttribute("href", /publication=.*version=.*revision=.*passage=/);
  await expect(questionRow.getByText("Published reference — confirm that it applies before submitting this answer.")).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.resolve("../.impeccable/review", `grounding-answer-${testInfo.project.name}.png`), fullPage: true });
});
