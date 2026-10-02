import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const apiUrl = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;
const releasesUrl = `${apiUrl}/architecture-knowledge/releases`;

type Release = { id: string; name: string | null; revision: number; status: "draft" | "published" };

/** Every version these specs start is named with this, so cleanup never touches anyone else's. */
const SMOKE_VERSION = "Smoke:";

/** Only one version can be in progress; remove any a previous test or retry left behind. */
async function removeDrafts(request: APIRequestContext) {
  const releases: Release[] = await (await request.get(releasesUrl)).json();
  for (const release of releases.filter((item) => item.status === "draft" && item.name?.startsWith(SMOKE_VERSION))) {
    const removed = await request.delete(`${releasesUrl}/${release.id}`,
      { data: { expected_revision: release.revision } });
    expect(removed.ok()).toBeTruthy();
  }
}

/** Below `lg` the Change desk folds to a one-line summary; open it so its steps can be reached. */
async function openDesk(page: Page) {
  const desk = page.getByRole("complementary", { name: "Change desk" });
  await expect(desk).toBeVisible();
  const toggle = desk.locator("button[aria-expanded]").first();
  if (await toggle.isVisible() && await toggle.getAttribute("aria-expanded") === "false") await toggle.click();
}

async function startVersion(page: Page, label: string) {
  const name = `${SMOKE_VERSION} ${label}`;
  await removeDrafts(page.request);
  await page.goto("/architecture-knowledge");
  await expect(page.getByRole("heading", { name: "Architecture catalogue", level: 1 })).toBeVisible();
  await openDesk(page);
  await page.getByRole("button", { name: "Start a new version", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Start a new version" });
  await dialog.getByLabel("Version name").fill(name);
  await dialog.getByRole("button", { name: "Start version" }).click();
  await expect(dialog).toBeHidden();
  await openDesk(page);
  await expect(page.getByRole("heading", { name, level: 2 })).toBeVisible();
  return name;
}

async function openStep(page: Page, label: string) {
  await openDesk(page);
  await page.getByRole("navigation", { name: "Steps to publish this version" })
    .getByRole("button", { name: new RegExp(`^Step \\d: ${label}`) }).click();
}

test("maintainer edits, indexes, previews, and publishes bilingual knowledge", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  const project = testInfo.project.name;
  const versionLabel = `bilingual ${project} ${Date.now()}`;
  const uniqueName = `New SMB system ${project}`;
  const arabicName = `نظام جديد ${project}`;
  const documentTitle = `Architecture notes ${project}`;
  const versionName = await startVersion(page, versionLabel);

  await openStep(page, "Add content");
  await expect(page.getByRole("heading", { name: "Add content", level: 2 })).toBeVisible();
  await page.getByRole("tab", { name: "Edit manually" }).click();
  await page.getByRole("button", { name: "Add system" }).click();
  const drawer = page.getByRole("dialog", { name: "Add a system" });
  await drawer.getByRole("textbox", { name: "Name (required)", exact: true }).fill(uniqueName);
  await drawer.getByLabel("Arabic name").fill(arabicName);
  await drawer.getByRole("textbox", { name: "System ID (required)" }).fill(`new-system-${project}`);
  const aliases = drawer.getByLabel("Other names");
  await aliases.pressSequentially(`first-${project}`);
  await aliases.press("Enter");
  await aliases.pressSequentially(`second-${project}`);
  await aliases.press("Enter");
  await expect(drawer.getByText(`first-${project}`, { exact: true })).toBeVisible();
  await expect(drawer.getByText(`second-${project}`, { exact: true })).toBeVisible();
  await drawer.getByRole("button", { name: "Add capability" }).click();
  await drawer.getByRole("textbox", { name: "Capability 1 Name (required)" }).fill("Ordering");
  await drawer.getByRole("textbox", { name: "Capability 1 ID (required)" }).fill("ordering");
  const phrases = drawer.getByRole("textbox", { name: /^Capability 1 Matching phrases/ });
  await phrases.pressSequentially("order,request,");
  await expect(drawer.getByRole("button", { name: "Capability 1: Ordering, ID ordering, no domain, 2 matching phrases" }))
    .toBeVisible();
  await drawer.getByRole("button", { name: "Add constraint" }).click();
  await drawer.getByLabel("Constraint 1", { exact: true }).fill("one");
  await drawer.getByLabel("Constraint 1", { exact: true }).press("Enter");
  await drawer.getByLabel("Constraint 2", { exact: true }).fill("two");
  await drawer.getByRole("button", { name: "Save system" }).click();
  await expect(drawer).toBeHidden();
  await expect(page.getByRole("status").filter({ hasText: "Version saved." })).toBeVisible();
  await expect(page.getByRole("button", { name: uniqueName, exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "From documents" }).click();
  await page.getByLabel("Document language").selectOption("mixed");
  await page.locator('input[type="file"][aria-label="Add documents"]').setInputFiles({
    name: `${documentTitle}.txt`, mimeType: "text/plain",
    buffer: Buffer.from(`${arabicName} supports SMB ordering. ${uniqueName} owns no squad.`),
  });
  await expect(page.getByRole("status").filter({ hasText: "1 document added." })).toBeVisible();
  const sources = page.getByRole("list", { name: "Source documents in this version" });
  await expect(sources.getByRole("listitem").filter({ hasText: documentTitle })).toContainText("English and Arabic");

  await openStep(page, "Build evidence index");
  await page.getByRole("button", { name: "Build evidence index", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "The index matches the latest changes." }))
    .toBeVisible({ timeout: 30_000 });

  const releases: (Release & { status: string })[] = await (await page.request.get(releasesUrl)).json();
  const releaseId = releases.find((release) => release.name === versionName)!.id;
  // The workbench previews impact rather than raw passages; the passage a mapping
  // cites comes from the same retrieval the mapping uses.
  const preview = await page.request.post(`${releasesUrl}/${releaseId}/preview`, { data: { query: arabicName } });
  expect(preview.ok()).toBeTruthy();
  const evidence: { id: string; source_label: string }[] = await preview.json();
  const citation = evidence.find((item) => item.source_label.includes(documentTitle))?.id;
  expect(citation).toBeTruthy();

  await openStep(page, "Publish");
  await page.getByLabel("What did you check?").fill("Reviewed bilingual source and catalogue.");
  await page.getByRole("button", { name: "Publish this version" }).click();
  await page.getByRole("dialog", { name: "Publish this version?" }).getByRole("button", { name: "Publish", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Published. Requirement mapping now uses this version." }))
    .toBeVisible();

  await page.goto(`/architecture-knowledge/releases/${releaseId}/evidence/${citation}`);
  await expect(page.getByRole("heading", { name: "Mapping evidence" })).toBeVisible();
  await expect(page.getByText(`${arabicName} supports SMB ordering.`)).toBeVisible();
});

test("reader sees no architecture maintenance controls", async ({ page }) => {
  await page.route("**/api/identity/me", route => void route.fulfill({
    status: 200, contentType: "application/json",
    body: JSON.stringify({ id: "reader", display_name: "Reader", email: null,
      roles: ["knowledge_reader"] }),
  }));
  await page.goto("/architecture-knowledge");
  await expect(page.getByRole("heading", { name: "Architecture catalogue", level: 1 })).toBeVisible();
  await openDesk(page);
  await expect(page.getByText("Read-only. Changes are made by knowledge maintainers in a new version.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Start a new version", exact: true })).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Steps to publish this version" })).toHaveCount(0);
});

/** A version in progress, on Add content > Edit manually, whose saves all fail with a conflict. */
async function failingManualEdits(page: Page, name: string) {
  await startVersion(page, name);
  await openStep(page, "Add content");
  await page.getByRole("tab", { name: "Edit manually" }).click();
  await page.route("**/api/architecture-knowledge/releases/*", async route => {
    if (route.request().method() !== "PUT") return route.continue();
    await route.fulfill({ status: 409, contentType: "application/json",
      body: JSON.stringify({ detail: "The draft changed; reload before saving." }) });
  });
}

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await removeDrafts(page.request);
});

test("failed system save preserves form input", async ({ page }, testInfo) => {
  await failingManualEdits(page, `failed system save ${testInfo.project.name} ${Date.now()}`);
  await page.getByRole("button", { name: "Add system" }).click();
  const drawer = page.getByRole("dialog", { name: "Add a system" });
  await drawer.getByRole("textbox", { name: "Name (required)", exact: true }).fill("Squad A gateway");
  await drawer.getByRole("button", { name: "Save system" }).click();
  await expect(drawer.getByRole("alert")).toContainText("draft changed");
  await expect(drawer.getByRole("textbox", { name: "Name (required)", exact: true })).toHaveValue("Squad A gateway");
  await expect(drawer.getByRole("textbox", { name: "System ID (required)" })).toHaveValue("squad-a-gateway");
});

test("failed dependency save preserves form input", async ({ page }, testInfo) => {
  await failingManualEdits(page, `failed dependency save ${testInfo.project.name} ${Date.now()}`);
  await page.getByRole("combobox", { name: "From system (required)", exact: true }).selectOption("bcrm");
  await page.getByRole("combobox", { name: "Depends on (required)", exact: true }).selectOption("gis");
  await page.getByRole("textbox", { name: "For what (required)" }).fill("Checks coverage");
  await page.getByRole("combobox", { name: "How", exact: true }).selectOption({ label: "Calls its API" });
  await page.getByRole("button", { name: "Add dependency" }).click();
  await expect(page.getByRole("alert")).toContainText("draft changed");
  await expect(page.getByRole("combobox", { name: "From system (required)", exact: true })).toHaveValue("bcrm");
  await expect(page.getByRole("combobox", { name: "Depends on (required)", exact: true })).toHaveValue("gis");
  await expect(page.getByRole("textbox", { name: "For what (required)" })).toHaveValue("Checks coverage");
  await expect(page.getByRole("combobox", { name: "How", exact: true })).toHaveValue("calls_api");
});
