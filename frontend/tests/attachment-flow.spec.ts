import { expect, test } from "@playwright/test";

test("Business need files survive draft resume and drive attachment-only analysis", async ({ page }, testInfo) => {
  await page.goto("/requirements/new");
  await page.getByLabel(/Requirement title/).fill(`Attachment source ${testInfo.project.name} ${Date.now()}`);
  await page.getByLabel("Attach files", { exact: true }).setInputFiles([
    { name: "business-need.md", mimeType: "text/markdown", buffer: Buffer.from("# Business need\nEnable SMB customers to order broadband bundles through the web channel.") },
    { name: "constraints.txt", mimeType: "text/plain", buffer: Buffer.from("Campaign launch before Q4. Only covered areas qualify.") },
  ]);
  await expect(page.getByRole("checkbox", { name: "Include in analysis" })).toHaveCount(2);
  for (const checkbox of await page.getByRole("checkbox", { name: "Include in analysis" }).all()) await expect(checkbox).toBeChecked();
  await expect(page.getByText("Ready for analysis", { exact: true })).toBeVisible();
  await expect(page.getByLabel(/Business need/)).toHaveValue("");
  await page.screenshot({ path: testInfo.outputPath("business-need-attachments.png"), fullPage: true });
  await page.getByRole("button", { name: "Save draft and exit" }).click();
  await expect(page).toHaveURL(/\/$/);
  const response = await page.request.get("/api/requirements/drafts");
  const drafts = await response.json() as Array<{ id: string; title: string }>;
  const draft = drafts.find((item) => item.title.startsWith(`Attachment source ${testInfo.project.name}`));
  expect(draft).toBeDefined();
  await page.goto(`/requirements/new?draft=${draft!.id}`);
  await expect(page.getByRole("checkbox", { name: "Include in analysis" })).toHaveCount(2);
  await expect(page.getByText("Ready for analysis", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Save and analyse", exact: true }).click();
  await expect(page).toHaveURL(/\/requirements\/[^/]+\/clarify$/);
  await expect(page.getByRole("heading", { name: "Known facts" })).toBeVisible({ timeout: 30_000 });
});


test("saved source readiness updates when the last attachment is excluded", async ({ page }) => {
  const draftResponse = await page.request.post("/api/requirements/drafts", { data: { title: `Design source ${Date.now()}` } });
  const draft = await draftResponse.json() as { id: string; version: number };
  await page.request.post(`/api/requirement-drafts/${draft.id}/attachments`, {
    multipart: { include_in_analysis: "true", file: { name: "need.md", mimeType: "text/markdown", buffer: Buffer.from("SMB customers order bundles online.") } },
  });
  const promoted = await page.request.post(`/api/requirements/drafts/${draft.id}/promote`, { data: { expected_version: draft.version } });
  expect(promoted.ok()).toBeTruthy();
  const requirement = await promoted.json() as { id: string };
  await page.goto(`/requirements/${requirement.id}/capture`);
  await expect(page.getByText("Ready for analysis", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: "Include in analysis" }).uncheck();
  await expect(page.getByText("Not ready for analysis", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue to analysis" })).toHaveAttribute("aria-disabled", "true");
  await page.getByRole("checkbox", { name: "Include in analysis" }).check();
  await expect(page.getByText("Ready for analysis", { exact: true })).toBeVisible();
});
