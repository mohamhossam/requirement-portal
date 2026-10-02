import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

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
