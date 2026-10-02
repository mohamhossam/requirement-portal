import { expect } from "@playwright/test";
import { test } from "./library-fixture";
import { execFileSync } from "node:child_process";
import path from "node:path";

for (const includeHeading of [false, true]) {
  test(`Word prose correction and heading ${includeHeading ? "correction" : "exclusion"} keep shared metadata clean`, async ({ page, request }, testInfo) => {
    if (testInfo.project.name === "responsive-chromium") await page.setViewportSize({ width: 390, height: 1000 });
    const root = path.resolve(import.meta.dirname, "../..");
    const python = process.env.SMOKE_PYTHON ?? (process.platform === "win32" ? path.join(root, ".venv/Scripts/python.exe") : "python");
    const buffer = execFileSync(python, ["-c", "import sys; from tests.word_table_fixtures import reviewed_word_prose_document; sys.stdout.buffer.write(reviewed_word_prose_document())"], { cwd: root });
    const title = `Word prose policy ${crypto.randomUUID()}`;
    await page.goto("/documents/library");
    await page.getByLabel("Document title", { exact: true }).fill(title);
    await page.getByLabel("Original file", { exact: true }).setInputFiles({
      name: "policy.docx",
      mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      buffer,
    });
    await page.getByRole("button", { name: "Upload for private review" }).click();
    await expect(page.getByRole("heading", { name: "Review extracted passages" })).toBeVisible({ timeout: 30000 });
    await expect(page.getByText(/Word headings, paragraphs and list items use neutral/).first()).toBeVisible();
    const passages = page.getByRole("textbox", { name: "Reviewed text", exact: true });
    await expect(passages).toHaveCount(5);
    await expect(passages.nth(1)).toHaveValue("Private paragraph XGPON التغطية مطلوبة.");
    await passages.nth(1).fill("Reviewed paragraph XGPON التغطية مطلوبة.");
    await passages.nth(2).fill("Reviewed list");
    if (includeHeading) await passages.nth(0).fill("Reviewed heading");
    for (const index of includeHeading ? [3, 4] : [0, 3, 4]) {
      await page.getByRole("checkbox", { name: "Include in shared publication" }).nth(index).uncheck();
    }
    const reasons = page.getByLabel("Reason for exclusion");
    for (let index = 0; index < (includeHeading ? 2 : 3); index++) await reasons.nth(index).fill("Outside approved shared policy");
    await page.getByLabel("Review summary").fill("Corrected Word prose and reviewed heading applicability");
    await page.getByRole("button", { name: "Save extraction review" }).click();
    await page.getByRole("button", { name: "Preview table-aware version" }).click();
    const build = page.locator("section").filter({ has: page.getByRole("heading", { name: "Build table-aware search version" }) });
    await expect(build.getByText("Reviewed paragraph XGPON التغطية مطلوبة.", { exact: true }).first()).toBeVisible();
    await expect(build.getByText(/Private|Never publish/)).toHaveCount(0);
    await build.screenshot({ path: testInfo.outputPath(`word-prose-${includeHeading}-preview.png`) });
    await page.getByRole("button", { name: "Approve and build search version" }).click();
    await expect(page.getByText(/Build ready · \d+ chunks/)).toBeVisible({ timeout: 30000 });
    await page.getByRole("checkbox", { name: "I understand that previous citations will need reconciliation." }).check();
    await page.getByRole("button", { name: "Activate built version" }).click();
    await expect(page.getByText("Published and searchable", { exact: true })).toBeVisible();
    await page.getByLabel("Search text", { exact: true }).fill("XGPON");
    await page.getByRole("button", { name: "Search published passages" }).click();
    const results = page.getByRole("region", { name: "Search results" });
    const citation = results.getByRole("link", { name: `${title} · version 1 · Paragraph 2` }).first();
    await expect(citation).toBeVisible();
    await expect(results.getByText(/Private|Never publish/)).toHaveCount(0);
    const documentId = new URL(page.url()).pathname.split("/").at(-1);
    const apiRoot = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;
    const publicResponse = await request.get(`${apiRoot}/library/documents/${documentId}`, { headers: { "X-Fake-Actor-Id": "fake-observer" } });
    expect(publicResponse.ok()).toBe(true);
    const publicDocument = await publicResponse.json();
    expect(publicDocument.versions[0].blocks).toHaveLength(includeHeading ? 3 : 2);
    expect(publicDocument.versions[0].blocks[0].section_path).toEqual(["Heading at paragraph 1"]);
    expect(JSON.stringify(publicDocument)).not.toMatch(/Private|Never publish/);
    const searchResponse = await request.post(`${apiRoot}/knowledge/search`, { data: { query: "XGPON" } });
    expect(searchResponse.ok()).toBe(true);
    const matches = (await searchResponse.json()).filter((item: { document_id: string }) => item.document_id === documentId);
    expect(matches.length).toBeGreaterThan(0);
    expect(JSON.stringify(matches)).not.toMatch(/Private|Never publish/);
    await page.goto((await citation.getAttribute("href"))!);
    const cited = page.getByRole("region", { name: "Cited published passage" });
    await expect(cited.getByRole("heading", { name: "Paragraph 2" })).toBeVisible();
    await expect(cited.getByText(/Private|Never publish/)).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}
