import { type APIRequestContext, expect, type Page, test } from "@playwright/test";

/*
 * The platform as one product (ADR-0098, ADR-0099): requirement work and the knowledge portal
 * behind one edge, offline with fake identity. A knowledge admin publishes a library passage in
 * the knowledge portal; anyone in requirement work reads it as a citation, read-only; only
 * knowledge admins cross into the portal.
 */

const ADMIN = { "X-Fake-Actor-Id": "fake-owner" };
const TEXT = "Fibre coverage is checked before every activation.";

type Citation = { document: string; publication: string; version: string; revision: string; passage: string };

async function published(request: APIRequestContext): Promise<Citation> {
  const uploaded = await request.post("/knowledge-api/library/ingestions", {
    headers: ADMIN,
    multipart: {
      title: "Platform citation check",
      idempotency_key: `platform-citation-${Date.now()}`,
      file: { name: "coverage.txt", mimeType: "text/plain", buffer: Buffer.from(TEXT) },
    },
  });
  expect(uploaded.status()).toBe(202);
  const path = `/knowledge-api/library/documents/${(await uploaded.json()).id}`;
  const read = async () => (await (await request.get(path, { headers: ADMIN })).json());
  // Uploads are scanned, then read.
  await expect.poll(async () => (await read()).versions[0].stage, { timeout: 300_000 }).toBe("ready_for_review");
  const view = await read();
  const source = view.versions[0];
  const reviewed = await request.post(`${path}/versions/${source.id}/review`, {
    headers: ADMIN,
    data: {
      expected_version: view.version,
      explanation: "Platform check",
      passages: source.blocks.map((block: { id: string; text: string }) => (
        { block_id: block.id, text: block.text, included: true, exclusion_reason: "" }
      )),
    },
  });
  expect(reviewed.ok()).toBe(true);
  const review = await reviewed.json();
  const revision = review.versions[0].revisions.at(-1).id;
  const approved = await request.post(`${path}/versions/${source.id}/approval`, {
    headers: ADMIN,
    data: { expected_version: review.version, revision_id: revision, fingerprint: review.review_fingerprint },
  });
  expect(approved.ok()).toBe(true);
  await expect.poll(async () => (await read()).published_id, { timeout: 60_000 }).toBeTruthy();
  const done = await read();
  return {
    document: done.id,
    publication: done.published_id,
    version: source.id,
    revision,
    passage: source.blocks[0].id,
  };
}

async function as(page: Page, actor: string) {
  await page.addInitScript((id) => {
    sessionStorage.setItem("requirement-ai.fake-actor", id);
    sessionStorage.setItem("knowledge-portal.fake-actor", id);
  }, actor);
}

let citation: Citation;

test.beforeAll(async ({ request }) => {
  citation = await published(request);
});

test("someone who is not a knowledge admin reads a cited passage, read-only", async ({ page }) => {
  await as(page, "fake-observer");
  const query = new URLSearchParams(citation).toString();
  await page.goto(`/references/passage?${query}`);

  const passage = page.getByRole("region", { name: "Cited published passage" });
  await expect(passage).toContainText(TEXT);
  await expect(page.getByRole("heading", { level: 1, name: "Platform citation check" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Knowledge portal" })).toHaveCount(0);
});

test("a knowledge admin crosses into the knowledge portal and finds the document", async ({ page }) => {
  await as(page, "fake-owner");
  await page.goto("/documents");
  await page.getByRole("link", { name: "Open knowledge portal" }).click();

  await expect(page).toHaveURL(/\/knowledge\/?$/);
  await page.goto("/knowledge/library");
  await expect(page.getByText("Platform citation check").first()).toBeVisible();
});

test("the knowledge portal turns away someone who is not a knowledge admin", async ({ page }) => {
  await as(page, "fake-observer");
  await page.goto("/knowledge/library");

  await expect(page.getByRole("heading", { level: 1, name: "This portal is for knowledge admins" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Go to Requirement AI" })).toBeVisible();
});
