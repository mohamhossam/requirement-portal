import { expect, test } from "@playwright/test";
import { analysisFixture } from "../src/test/fixtures";

const apiUrl = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;

test("source details stay quiet, accessible and local on desktop and mobile", async ({ page }, testInfo) => {
  const created = await page.request.post(`${apiUrl}/requirements`, { data: {
    title: "Source presentation smoke", description: "Clarify the DEL and PABX voice plans.",
  } });
  expect(created.ok()).toBeTruthy();
  const requirement = await created.json() as { id: string };
  const reference = { document_id: "source-document", version_id: "source-version", checksum_sha256: "a".repeat(64), block_id: "table-4-row-7", label: "[BUC1] Introduction of New Building Block in BFM Voice Component – DEL/PABX → Table 4, row 7" };
  const answer = { question_id: "answered-1", kind: "open_question", subject: "Who uses DEL?", answer: "DEL is a single-user line plan.", answered_by: { id: "fake-owner", display_name: "Amina Owner", email: null }, answered_at: "2026-09-18T10:00:00Z", source_suggestion_id: null };
  await page.route(`**/requirements/${requirement.id}/analysis`, (route) => route.fulfill({ json: {
    ...analysisFixture, requirement_id: requirement.id, known_facts: [{ statement: answer.answer, evidence_references: [reference, reference] }],
    document_references: [{ ...reference, filename: "SMB Voice Business Requirement.docx" }],
    clarifications: [answer, { ...answer, question_id: "answered-2", subject: "What is the DEL plan?" }],
    clarification_evidence: [{ evidence_key: `known_fact:${answer.answer.toLowerCase()}`, clarification_numbers: [1, 1, 2] }],
  } }));
  await page.goto(`/requirements/${requirement.id}/clarify`);
  const trigger = page.getByRole("button", { name: `Where this came from: ${answer.answer}` });
  await expect(trigger).toHaveText(/1 document reference · 2 human answers/);
  await expect(page.getByText(reference.label, { exact: true })).toHaveCount(0);
  const requests: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/api/")) requests.push(request.url()); });
  await trigger.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Where this came from", exact: true });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Close", exact: true })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.locator("summary")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: "Close", exact: true })).toBeFocused();
  await expect(dialog.getByText(reference.label, { exact: true })).toBeVisible();
  await expect(dialog.getByRole("region", { name: "Human answers" }).getByText(/Amina Owner/)).toHaveCount(2);
  await expect(dialog.getByRole("link", { name: /Open this passage/ })).toHaveAttribute("href", "/documents/source-document#block-table-4-row-7");
  await expect(dialog.getByRole("link", { name: /Open this passage/ })).toHaveAttribute("target", "_blank");
  await expect(dialog.locator("details")).not.toHaveAttribute("open", "");
  await dialog.getByText("Exact reference").click();
  await expect(dialog.getByText("source-version", { exact: true })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: "Close", exact: true })).toBeFocused();
  await page.screenshot({ path: testInfo.outputPath("source-panel-desktop.png") });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
  expect(requests.filter((url) => /\/documents\/|\/analysis(?:\?|$)|\/epic|\/features|\/stories|\/revisions/.test(url))).toEqual([]);
  await trigger.click();
  await page.mouse.click(20, 250);
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();

  await page.setViewportSize({ width: 390, height: 844 });
  await trigger.click();
  await expect(dialog).toBeVisible();
  const bounds = await dialog.boundingBox();
  expect(bounds?.x).toBe(0);
  expect(bounds?.width).toBe(390);
  expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath("source-panel-mobile.png") });
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await expect(trigger).toBeFocused();
});
