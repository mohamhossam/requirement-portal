import { expect, test, type Page } from "@playwright/test";
import { analysisFixture, approvedFeatureFixture, epicFixture, featureSetFixture, storySetFixture, storyQualityFixture } from "../src/test/fixtures";
import { jobFixture } from "../src/test/jobFixture";

const apiUrl = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;

async function workspace(page: Page, active = false) {
  const response = await page.request.post(`${apiUrl}/requirements`, { maxRetries: 1, data: { title: "Focused backlog smoke", description: "Review eligible SMB ordering and fulfilment." } });
  expect(response.ok()).toBeTruthy();
  const requirement = await response.json() as { id: string };
  let polls = 0;
  const reads: string[] = [];
  page.on("request", (request) => { if (request.method() === "GET" && request.url().includes("/api/requirements/")) reads.push(request.url()); });
  const base = `/requirements/${requirement.id}`;
  await page.route(`**${base}/analysis`, (route) => route.fulfill({ json: { ...analysisFixture, requirement_id: requirement.id, human_confirmed: true, confirmed_at: "2026-09-18T10:00:00Z" } }));
  await page.route(`**${base}/epic`, (route) => route.fulfill({ json: { ...epicFixture, requirement_id: requirement.id, status: "approved" } }));
  await page.route(`**${base}/features`, (route) => route.fulfill({ json: { ...featureSetFixture, features: [approvedFeatureFixture, featureSetFixture.features[1]] } }));
  await page.route(`**${base}/features/*/stories`, (route) => route.fulfill({ json: storySetFixture }));
  await page.route(`**${base}/features/*/stories/change-proposals`, (route) => route.fulfill({ json: [] }));
  await page.route(`**${base}/features/*/stories/quality-assessment`, (route) => route.fulfill({ json: { feature_id: "feature-1", source_fingerprint: "current", generated_at: "2026-09-18T10:00:00Z", fresh: true, stories: [storyQualityFixture] } }));
  await page.route(`**${base}/ai-jobs*`, (route) => { polls += 1; return route.fulfill({ json: active ? [{ ...jobFixture, requirement_id: requirement.id, operation: "generate_stories", status: "running" }] : [] }); });
  return { base, reads, polls: () => polls };
}

test("selects deep links, preserves drafts and reads only requested Stories", async ({ page }, testInfo) => {
  const { base, reads } = await workspace(page);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto(`${base}/breakdown/epic`);
  const detail = page.locator(".backlog-detail");
  await expect(detail.getByRole("heading", { name: epicFixture.name })).toBeVisible();
  expect(reads.filter((url) => /\/stories|\/story-quality|\/story-proposals/.test(url))).toEqual([]);
  expect(await detail.getByRole("heading", { name: epicFixture.name }).boundingBox()).toMatchObject({ x: expect.any(Number) });
  // Still above the fold, with the shared frame's header and page title above it
  // now rather than the Backlog's own compact header.
  expect((await detail.getByRole("heading", { name: epicFixture.name }).boundingBox())!.y).toBeLessThan(600);
  await expect(page.getByText("This version is already approved. Regenerate or edit it before approving again.")).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("epic-desktop.png") });
  await detail.getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByLabel("Epic name").fill("Unsaved Epic draft");
  await page.getByRole("navigation", { name: "Backlog items" }).getByRole("link", { name: /Digital ordering/ }).click();
  await expect(page).toHaveURL(new RegExp(`${base}/breakdown/features/feature-1$`));
  await expect(page.locator(".compact-story-list a").first()).toBeVisible();
  expect(reads.filter((url) => url.includes("/features/feature-2/stories"))).toEqual([]);
  await detail.locator(".feature-card:visible").getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByLabel("Feature name").fill("Unsaved Feature draft");
  await page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Epic", exact: true }).click();
  await expect(page.getByLabel("Epic name")).toBeVisible();
  await expect(page.getByLabel("Epic name")).toHaveValue("Unsaved Epic draft");
  await detail.locator("form:visible").getByRole("button", { name: "Cancel", exact: true }).click();
  await page.goBack();
  await expect(page.getByLabel("Feature name")).toBeVisible();
  await expect(page.getByLabel("Feature name")).toHaveValue("Unsaved Feature draft");
  await detail.locator("form:visible").getByRole("button", { name: "Cancel", exact: true }).click();
  await page.goBack();
  // `h2`, not `h3`: the page `h1` is the requirement's own title, so the Epic
  // is the subject of this route rather than a third level inside it.
  await expect(detail.locator(".epic-card h2")).toBeVisible();
  await page.goForward();
  await expect(page.locator(".compact-story-list a").first()).toBeVisible();
  const firstStory = storySetFixture.stories[0]!;
  await page.locator(".compact-story-list a").first().click();
  await expect(page).toHaveURL(new RegExp(`/stories/${firstStory.id}$`));
  await expect(detail.locator(".story-card:visible")).toContainText(firstStory.voice);
  await detail.locator(".story-card:visible").getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByLabel("So that", { exact: true }).fill("An unsaved Story benefit");
  await page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Digital ordering", exact: true }).click();
  await page.locator(".compact-story-list a").first().click();
  await expect(page.getByLabel("So that", { exact: true })).toBeVisible();
  await expect(page.getByLabel("So that", { exact: true })).toHaveValue("An unsaved Story benefit");
  await detail.locator("form:visible").getByRole("button", { name: "Cancel", exact: true }).click();
  const criteria = () => detail.locator(".story-card:visible")
    .getByRole("heading", { name: "Acceptance criteria" }).locator("xpath=following-sibling::ol[1]");
  await expect(criteria()).toContainText("Given");
  await page.reload();
  await expect(detail.locator(".story-card:visible")).toContainText(firstStory.voice);
  await expect(detail.getByText(/^Successful checks/)).toBeVisible();
  await expect(detail.getByText(/^Successful checks/).locator("..")).not.toHaveAttribute("open", "");
  // The way on is the Story pager, not a filled link out to Review & approve.
  await expect(detail.getByRole("navigation", { name: "Story position" })
    .getByRole("link", { name: /^(Next Story|Next Feature|Go to Review & approve)/ })).toBeVisible();
  await expect(criteria().getByRole("listitem").first().locator("span").first()).toHaveCSS("font-size", "16px");
  await expect(detail.locator(".story-card:visible").getByRole("region", { name: "INVEST quality review" })
    .locator("li p").first()).toHaveCSS("font-size", "16px");
  await page.screenshot({ path: testInfo.outputPath("story-desktop.png") });
  await page.goto(`${base}/breakdown/features/missing`);
  await expect(page.getByRole("heading", { name: "Feature not found" })).toBeVisible();
  await page.goto(`${base}/breakdown/features/feature-1/stories/missing`);
  await expect(page.getByRole("heading", { name: "Story not found" })).toBeVisible();
});

test("supports mobile drawers, merge mode, zoom and one polling owner", async ({ page }, testInfo) => {
  const { base, polls } = await workspace(page, true);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${base}/breakdown/epic`);
  await expect(page.getByRole("heading", { name: epicFixture.name })).toBeVisible();
  await page.getByRole("button", { name: "Browse backlog" }).click();
  const drawer = page.getByRole("dialog", { name: "Browse backlog", exact: true });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByRole("button", { name: "Close", exact: true })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(drawer.getByRole("link", { name: /Service fulfilment/ })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(drawer.getByRole("button", { name: "Close", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Browse backlog" })).toBeFocused();
  await page.getByRole("button", { name: "Browse backlog" }).click();
  await drawer.getByRole("link", { name: /Digital ordering/ }).click();
  await expect(drawer).toHaveCount(0);
  await expect(page.locator(".compact-story-list a").first()).toBeVisible();
  await expect(page.getByRole("checkbox")).toHaveCount(0);
  await page.getByRole("button", { name: "Select Stories", exact: true }).click();
  await expect(page.getByRole("checkbox")).toHaveCount(storySetFixture.stories.length);
  await page.getByRole("button", { name: "Cancel selection" }).click();
  await expect(page.getByRole("checkbox")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath("feature-mobile.png") });
  const before = polls();
  await page.waitForTimeout(2300);
  expect(polls() - before).toBeGreaterThanOrEqual(2);
  expect(polls() - before).toBeLessThanOrEqual(3);
  await page.setViewportSize({ width: 640, height: 360 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath("workspace-200-percent-equivalent.png") });
  await page.evaluate(() => { document.body.style.zoom = "2"; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath("workspace-200-percent-css-zoom.png") });
});


test("keeps source impact warnings inside the drawer and resets drafts across actors", async ({ page }) => {
  const { base } = await workspace(page);
  await page.goto(`${base}/breakdown`);
  await expect(page.locator(".epic-card h2")).toBeVisible();
  await page.getByRole("button", { name: "Source document", exact: true }).click();
  const source = page.getByRole("dialog", { name: "Source document", exact: true });
  await source.getByRole("button", { name: "Edit source", exact: true }).click();
  await source.getByLabel(/Requirement title/).fill("Changed source draft");
  await page.route(`**${base}/impact-preview`, (route) => route.fulfill({ json: { requirement_id: base.split("/").at(-1), requirement_version: 1, source_changed: true, requires_acknowledgement: true, analysis_count: 1, epic_count: 1, feature_count: 2, story_count: 2 } }));
  await source.getByRole("button", { name: "Save requirement" }).click();
  const warning = source.getByRole("dialog", { name: "Save source changes?" });
  await expect(warning).toContainText("1 Epic, 2 Features, and 2 Stories stale");
  await expect(warning.getByRole("button", { name: "Acknowledge and save" })).toBeVisible();
  // The opening focus goes to the safe action, not the irreversible one: this
  // dialog confirms a save that marks downstream work stale, and Enter is the key
  // a person is most likely still holding from whatever opened it. Cancel is also
  // first in DOM order, so Tab moves forward onto the confirm.
  await expect(warning.getByRole("button", { name: "Cancel", exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(warning.getByRole("button", { name: "Acknowledge and save" })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(warning.getByRole("button", { name: "Cancel", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(warning).toHaveCount(0);
  await expect(source).toBeVisible();
  await source.getByRole("button", { name: "Close", exact: true }).click();
  await page.locator(".backlog-detail").getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByLabel("Epic name").fill("Owner-only unsaved draft");
  await page.getByLabel("Development persona").selectOption("fake-observer");
  await expect(page.getByLabel("Epic name")).toHaveCount(0);
  await page.getByLabel("Development persona").selectOption("fake-owner");
  await expect(page.locator(".epic-card h2")).toHaveText(epicFixture.name);
  await page.locator(".backlog-detail").getByRole("button", { name: "Edit", exact: true }).click();
  await expect(page.getByLabel("Epic name")).toHaveValue(epicFixture.name);
});

test("shows loading and real failures, keeps stale Stories readable, and returns to a removed Story's Feature", async ({ page }) => {
  const { base } = await workspace(page);
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**${base}/epic`, async (route) => { await gate; await route.fulfill({ json: { ...epicFixture, status: "approved" } }); });
  await page.goto(`${base}/breakdown/epic`);
  await expect(page.getByRole("status", { name: "Loading the Epic" })).toBeAttached();
  release();
  await expect(page.locator(".epic-card h2")).toBeVisible();
  await page.route(`**${base}/features`, (route) => route.fulfill({ status: 503, json: { detail: "Backlog temporarily unavailable" } }));
  await page.reload();
  await expect(page.getByText(/Backlog temporarily unavailable/)).toBeVisible();
  await page.unroute(`**${base}/features`);
  await page.route(`**${base}/features`, (route) => route.fulfill({ json: { ...featureSetFixture, features: [{ ...approvedFeatureFixture, stale: { reason: "requirement_changed", since: "2026-09-18T10:00:00Z" } }] } }));
  let items = storySetFixture.stories;
  await page.route(`**${base}/features/feature-1/stories`, (route) => route.fulfill({ json: { ...storySetFixture, stories: items } }));
  await page.goto(`${base}/breakdown/features/feature-1/stories/${items[0]!.id}`);
  await expect(page.locator(".story-card:visible")).toContainText(items[0]!.voice);
  await expect(page.getByRole("button", { name: "Edit", exact: true })).toBeDisabled();
  // A terminal change job refreshes the observed set; the selected identifier disappeared.
  items = items.slice(1);
  await page.route(`**${base}/ai-jobs*`, (route) => route.fulfill({ json: [{ ...jobFixture, requirement_id: base.split("/").at(-1), status: "running", operation: "regenerate_story_set" }] }));
  await page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Digital ordering", exact: true }).click();
  await page.locator(".compact-story-list a").first().click();
  // Restore and observe both IDs, then emulate an applied replacement through a completed regeneration.
  items = storySetFixture.stories;
  await page.reload();
  await expect(page.locator(".story-card:visible")).toBeVisible();
  items = [];
  await page.route(`**${base}/ai-jobs*`, (route) => route.fulfill({ json: [{ ...jobFixture, requirement_id: base.split("/").at(-1), status: "succeeded", operation: "regenerate_story_set" }] }));
  await expect(page).toHaveURL(new RegExp(`${base}/breakdown/features/feature-1$`));
  await expect(page.getByRole("status").filter({ hasText: "The Story set changed" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "No Stories yet" })).toBeVisible();
});
