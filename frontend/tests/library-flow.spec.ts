import { expect } from "@playwright/test";
import { test } from "./library-fixture";

test("owner reviews, publishes, searches and withdraws exact reference passages", async ({ page }, testInfo) => {
  await page.goto("/documents/library");
  const title = `Eligibility ${testInfo.project.name} ${Date.now()}`;
  await page.getByLabel("Document title", { exact: true }).fill(title);
  await page.getByLabel("Original file", { exact: true }).setInputFiles({ name: "eligibility.txt", mimeType: "text/plain", buffer: Buffer.from("XGPON coverage is required for ordering.\nPrivate operational note.\nBCRM and CPP are supported ordering channels.") });
  await page.getByRole("button", { name: "Upload for private review" }).click();
  await expect(page.getByRole("heading", { name: "Review extracted passages" })).toBeVisible({ timeout: 30000 });
  await page.getByRole("checkbox", { name: "Include in shared publication" }).nth(1).uncheck();
  await page.getByLabel("Reason for exclusion").fill("Not part of shared policy");
  await page.getByLabel("Review summary").fill("Compared against original");
  await page.getByRole("button", { name: "Save extraction review" }).click();
  await page.getByRole("button", { name: "Preview saved retrieval chunks" }).click();
  await expect(page.getByText("2 chunks from the saved review")).toBeVisible();
  await page.getByRole("textbox", { name: "Reviewed text", exact: true }).first().fill("XGPON coverage is required before ordering.");
  await expect(page.getByRole("button", { name: "Approve saved revision" })).toBeDisabled();
  await expect(page.getByText("You have unsaved passage changes.", { exact: false })).toBeVisible();
  await page.getByRole("textbox", { name: "Reviewed text", exact: true }).first().fill("XGPON coverage is required for ordering.");
  await page.getByLabel("Review summary").fill("Verified final revision");
  await page.getByRole("button", { name: "Save extraction review" }).click();
  await expect(page.getByRole("button", { name: "Approve saved revision" })).toBeEnabled();
  await page.getByRole("button", { name: "Approve saved revision" }).click();
  await expect(page.getByText("Published and searchable", { exact: true })).toBeVisible({ timeout: 30000 });
  await page.getByLabel("Search text", { exact: true }).fill("XGPON");
  await page.getByRole("button", { name: "Search published passages" }).click();
  const results = page.getByRole("region", { name: "Search results" });
  const result = results.getByRole("link", { name: `${title} · version 1 · Line 1`, exact: true }).locator("..");
  await expect(result.getByText("XGPON coverage is required for ordering.", { exact: true })).toBeVisible();
  await result.getByText(/Surrounding approved context · 2 passages/).click();
  await expect(result.getByText("BCRM and CPP are supported ordering channels.", { exact: false })).toBeVisible();
  await expect(result.getByText("Private operational note.")).toHaveCount(0);
  await page.evaluate(() => { if (document.activeElement instanceof HTMLElement) document.activeElement.blur(); window.scrollTo(0, 0); });
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  await page.screenshot({ path: testInfo.outputPath("library-published.png"), fullPage: true });
  await page.getByLabel("Why is this evidence no longer safe to use?").fill("Superseded policy");
  await page.getByRole("button", { name: "Withdraw from search now" }).click();
  await expect(page.getByText("Withdrawn from shared search", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Search results" })).toHaveCount(0);
});

test("citation opens passage 21 from the still-published version during replacement", async ({ page, request }) => {
  const apiUrl = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;
  const unique = crypto.randomUUID();
  const lines = Array.from({ length: 20 }, (_, i) => `Background statement ${i + 1}.`);
  const citedText = `CITATION${unique.replaceAll("-", "")} coverage policy.`;
  lines.push(citedText);
  const upload = await request.post(`${apiUrl}/library/ingestions`, { multipart: {
    title: `Citation policy ${unique}`, idempotency_key: unique,
    file: { name: "policy.txt", mimeType: "text/plain", buffer: Buffer.from(lines.join("\n")) },
  } });
  expect(upload.status()).toBe(202);
  const initial = await upload.json();
  const path = `${apiUrl}/library/documents/${initial.id}`;
  await expect.poll(async () => (await (await request.get(path)).json()).versions[0].stage).toBe("ready_for_review");
  const extracted = await (await request.get(path)).json();
  const source = extracted.versions[0];
  const reviewed = await (await request.post(`${path}/versions/${source.id}/review`, { data: {
    expected_version: extracted.version, explanation: "Browser fixture review",
    passages: source.blocks.map((b: { id: string; text: string }) => ({ block_id: b.id, text: b.text, included: true, exclusion_reason: "" })),
  } })).json();
  const approval = await request.post(`${path}/versions/${source.id}/approval`, { data: {
    expected_version: reviewed.version, revision_id: reviewed.versions[0].revisions[0].id,
    fingerprint: reviewed.review_fingerprint,
  } });
  expect(approval.ok()).toBeTruthy();
  await expect.poll(async () => (await (await request.get(path)).json()).published_id).toBeTruthy();
  const published = await (await request.get(path)).json();
  const replacement = await request.post(`${apiUrl}/library/ingestions`, { multipart: {
    title: initial.title, idempotency_key: crypto.randomUUID(), document_id: initial.id,
    expected_version: String(published.version),
    file: { name: "replacement.txt", mimeType: "text/plain", buffer: Buffer.from("Private replacement text.") },
  } });
  expect(replacement.status()).toBe(202);
  await page.goto("/documents/library");
  await page.getByLabel("Search text", { exact: true }).fill(citedText);
  await page.getByRole("button", { name: "Search published passages" }).click();
  await page.getByRole("region", { name: "Search results" }).getByRole("link", { name: `${initial.title} · version 1 · Line 21` }).click();
  const citation = page.getByRole("region", { name: "Cited published passage" });
  await expect(citation.getByText(citedText, { exact: true })).toBeVisible();
  await expect(citation.getByText("Published file version 1", { exact: false })).toBeVisible();
  await expect(citation.getByText("Private replacement text.")).toHaveCount(0);
});
