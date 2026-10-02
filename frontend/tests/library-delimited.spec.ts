import { expect } from "@playwright/test";
import { test } from "./library-fixture";

for (const kind of ["csv", "tsv"] as const) {
  test(`${kind.toUpperCase()} first record is independently excluded from publication`, async ({ page, request }, testInfo) => {
    if (testInfo.project.name === "responsive-chromium") await page.setViewportSize({ width: 390, height: 1000 });
    const delimiter = kind === "tsv" ? "\t" : ",";
    const mimeType = kind === "tsv" ? "text/tab-separated-values" : "text/csv";
    const buffer = Buffer.from("\ufeff" + [
      ["Private header", "Private conditions"],
      ["XGPON", '"' + "التغطية مطلوبة. ".repeat(80) + '\r\nCoverage required"'],
      ["Private appendix", "Never publish"],
    ].map((row) => row.join(delimiter)).join("\r\n"));
    const title = `${kind.toUpperCase()} policy ${crypto.randomUUID()}`;
    await page.goto("/documents/library");
    await page.getByLabel("Document title", { exact: true }).fill(title);
    await page.getByLabel("Original file", { exact: true }).setInputFiles({ name: `policy.${kind}`, mimeType, buffer });
    await page.getByRole("button", { name: "Upload for private review" }).click();
    await expect(page.getByRole("heading", { name: "Review extracted passages" })).toBeVisible({ timeout: 30000 });
    await expect(page.getByText(/headers are not inferred or copied/).first()).toBeVisible();
    const passages = page.getByRole("textbox", { name: "Reviewed text", exact: true });
    await expect(passages).toHaveCount(3);
    await expect(passages.nth(0)).toHaveValue(/Private header/);
    await expect(passages.nth(1)).toHaveValue(/R2C1: XGPON.*R2C2: التغطية مطلوبة/);
    for (const index of [0, 2]) {
      await page.getByRole("checkbox", { name: "Include in shared publication" }).nth(index).uncheck();
    }
    const reasons = page.getByLabel("Reason for exclusion");
    for (let index = 0; index < 2; index++) await reasons.nth(index).fill("Outside approved shared policy");
    await page.getByLabel("Review summary").fill("Checked logical records and excluded private header and appendix");
    await page.getByRole("button", { name: "Save extraction review" }).click();
    await page.getByRole("button", { name: "Preview table-aware version" }).click();
    const build = page.locator("section").filter({ has: page.getByRole("heading", { name: "Build table-aware search version" }) });
    await expect(build.getByText("Field label for context: R2C2:").first()).toBeVisible();
    await expect(build.getByText(/Private|Never publish/)).toHaveCount(0);
    await build.screenshot({ path: testInfo.outputPath(`${kind}-row-preview.png`) });
    await page.getByRole("button", { name: "Approve and build search version" }).click();
    await expect(page.getByText(/Build ready · \d+ chunks/)).toBeVisible({ timeout: 30000 });
    await page.getByRole("checkbox", { name: "I understand that previous citations will need reconciliation." }).check();
    await page.getByRole("button", { name: "Activate built version" }).click();
    await expect(page.getByText("Published and searchable", { exact: true })).toBeVisible();
    await page.getByLabel("Search text", { exact: true }).fill("XGPON");
    await page.getByRole("button", { name: "Search published passages" }).click();
    const results = page.getByRole("region", { name: "Search results" });
    const citation = results.getByRole("link", { name: `${title} · version 1 · Row 2` }).first();
    await expect(citation).toBeVisible();
    await expect(results.getByText(/Private|Never publish/)).toHaveCount(0);
    const documentId = new URL(page.url()).pathname.split("/").at(-1);
    const apiRoot = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;
    const publicResponse = await request.get(`${apiRoot}/library/documents/${documentId}`, { headers: { "X-Fake-Actor-Id": "fake-observer" } });
    expect(publicResponse.ok()).toBe(true);
    const publicDocument = await publicResponse.json();
    expect(publicDocument.versions[0].blocks).toHaveLength(1);
    expect(publicDocument.versions[0].blocks[0].label).toBe("Row 2");
    await page.goto((await citation.getAttribute("href"))!);
    const cited = page.getByRole("region", { name: "Cited published passage" });
    await expect(cited.getByRole("heading", { name: "Row 2" })).toBeVisible();
    await expect(cited.getByText(/Private|Never publish/)).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}
