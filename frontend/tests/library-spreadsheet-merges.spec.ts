import { expect } from "@playwright/test";
import { test } from "./library-fixture";
import { execFileSync } from "node:child_process";
import path from "node:path";

test("Spreadsheet merged rows retain positions without publishing excluded anchor or hidden-sheet text", async ({ page, request }, testInfo) => {
  if (testInfo.project.name === "responsive-chromium") await page.setViewportSize({ width: 390, height: 1000 });
  const root = path.resolve(import.meta.dirname, "../..");
  const python = process.env.SMOKE_PYTHON ?? (process.platform === "win32" ? path.join(root, ".venv/Scripts/python.exe") : "python");
  const buffer = execFileSync(python, ["-c", "import sys; from tests.spreadsheet_fixtures import reviewed_spreadsheet_document; sys.stdout.buffer.write(reviewed_spreadsheet_document())"], { cwd: root });
  const title = `Workbook policy ${crypto.randomUUID()}`;
  await page.goto("/documents/library");
  await page.getByLabel("Document title", { exact: true }).fill(title);
  await page.getByLabel("Original file", { exact: true }).setInputFiles({ name: "policy.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer });
  await page.getByRole("button", { name: "Upload for private review" }).click();
  await expect(page.getByRole("heading", { name: "Review extracted passages" })).toBeVisible({ timeout: 30000 });
  await expect(page.getByText(/anchor wording is not copied into continuation cells/).first()).toBeVisible();
  const passages = page.getByRole("textbox", { name: "Reviewed text", exact: true });
  await expect(passages).toHaveCount(6);
  await expect(passages.nth(3)).toHaveValue(/A3=\[merged A2:A3 continuation; anchor A2\] \| B3=XGPON التغطية مطلوبة/);
  await expect(passages.nth(5)).toHaveValue(/Private hidden rule/);
  for (const index of [0, 1, 2, 4, 5]) {
    await page.getByRole("checkbox", { name: "Include in shared publication" }).nth(index).uncheck();
  }
  const reasons = page.getByLabel("Reason for exclusion");
  for (let index = 0; index < 5; index++) await reasons.nth(index).fill("Outside approved shared policy");
  await page.getByLabel("Review summary").fill("Checked merged ranges and excluded private header, anchor and hidden worksheet");
  await page.getByRole("button", { name: "Save extraction review" }).click();
  await page.getByRole("button", { name: "Preview table-aware version" }).click();
  const build = page.locator("section").filter({ has: page.getByRole("heading", { name: "Build table-aware search version" }) });
  await expect(build.getByText("Field label for context: B3=").first()).toBeVisible();
  await expect(build.getByText(/Private|Internal/)).toHaveCount(0);
  await expect(build.locator(".library-passage > p.library-text").filter({ hasText: "A3=[merged A2:A3 continuation; anchor A2]" })).toBeVisible();
  await build.screenshot({ path: testInfo.outputPath("spreadsheet-merge-preview.png") });
  await page.getByRole("button", { name: "Approve and build search version" }).click();
  await expect(page.getByText(/Build ready · \d+ chunks/)).toBeVisible({ timeout: 30000 });
  await page.getByRole("checkbox", { name: "I understand that previous citations will need reconciliation." }).check();
  await page.getByRole("button", { name: "Activate built version" }).click();
  await expect(page.getByText("Published and searchable", { exact: true })).toBeVisible();
  await page.getByLabel("Search text", { exact: true }).fill("XGPON");
  await page.getByRole("button", { name: "Search published passages" }).click();
  const results = page.getByRole("region", { name: "Search results" });
  const citation = results.getByRole("link", { name: `${title} · version 1 · Worksheet 1!3:3` }).first();
  await expect(citation).toBeVisible();
  await expect(results.getByText(/Private|Internal/)).toHaveCount(0);
  const documentId = new URL(page.url()).pathname.split("/").at(-1);
  const apiRoot = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;
  const publicResponse = await request.get(`${apiRoot}/library/documents/${documentId}`, { headers: { "X-Fake-Actor-Id": "fake-observer" } });
  expect(publicResponse.ok()).toBe(true);
  const publicDocument = await publicResponse.json();
  expect(publicDocument.versions[0].blocks).toHaveLength(1);
  expect(publicDocument.versions[0].blocks[0].label).toBe("Worksheet 1!3:3");
  await page.goto((await citation.getAttribute("href"))!);
  const cited = page.getByRole("region", { name: "Cited published passage" });
  await expect(cited.getByRole("heading", { name: "Worksheet 1!3:3" })).toBeVisible();
  await expect(cited.getByText(/Private|Internal/)).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("Spreadsheet attachments expose merged continuations and retain hidden-sheet opt-in", async ({ page, request }, testInfo) => {
  if (testInfo.project.name === "responsive-chromium") await page.setViewportSize({ width: 390, height: 1000 });
  const root = path.resolve(import.meta.dirname, "../..");
  const python = process.env.SMOKE_PYTHON ?? (process.platform === "win32" ? path.join(root, ".venv/Scripts/python.exe") : "python");
  const buffer = execFileSync(python, ["-c", "import sys; from tests.spreadsheet_fixtures import reviewed_spreadsheet_document; sys.stdout.buffer.write(reviewed_spreadsheet_document())"], { cwd: root });
  const apiRoot = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;
  const created = await request.post(`${apiRoot}/requirements`, { data: { title: "Spreadsheet attachment", description: "Review workbook merge structure." } });
  expect(created.ok()).toBe(true);
  const requirement = await created.json();
  const filename = `merged-${crypto.randomUUID()}.xlsx`;
  await page.goto(`/requirements/${requirement.id}/capture`);
  await page.getByLabel("Attach files", { exact: true }).setInputFiles({ name: filename, mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer });
  await expect(page.getByRole("status").filter({ hasText: "Processing continues in the background" })).toBeVisible({ timeout: 30000 });
  await expect(page.getByRole("link", { name: `Review ${filename}`, exact: true })).toBeVisible({ timeout: 30000 });
  await page.goto("/documents");
  await page.getByRole("link", { name: new RegExp(filename) }).click();
  await expect(page.getByRole("heading", { name: "Outline", exact: true })).toBeVisible();
  // Worksheet ranges are drawn as the sheet they came from: row 3, the merged
  // continuation under column A and the coverage wording under column B.
  const mergedRow = page.getByRole("row")
    .filter({ has: page.getByRole("rowheader", { name: "3", exact: true }) })
    .filter({ hasText: "XGPON" });
  await expect(mergedRow.getByRole("cell", { name: "[merged A2:A3 continuation; anchor A2]", exact: true })).toBeVisible();
  await expect(page.getByText(/anchor wording is not copied into continuation cells/).first()).toBeVisible();
  // Hidden sheets are offered by their title, with the sheet's workbook name as the hint.
  const hiddenSheet = page.getByRole("group", { name: "Hidden worksheets" })
    .getByRole("checkbox", { name: "Internal", exact: true });
  await expect(hiddenSheet).toHaveAccessibleDescription(/Worksheet 2 in the workbook/);
  await expect(hiddenSheet).not.toBeChecked();
  await hiddenSheet.click();
  await expect(hiddenSheet).toBeChecked();
  await page.reload();
  await expect(hiddenSheet).toBeChecked();
  const originalViewport = page.viewportSize()!;
  for (const width of [360, 390, 740, 900, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), { message: `Attachment review fits viewport at ${width}px` }).toBe(true);
  }
  await page.setViewportSize(originalViewport);
  await page.screenshot({ path: testInfo.outputPath("spreadsheet-attachment.png"), fullPage: true });
});
