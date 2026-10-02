import { expect, test, type Page } from "@playwright/test";

const apiUrl = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;

/**
 * The band between the two project viewports, which nothing else renders.
 *
 * `chromium` runs at 1440 and `responsive-chromium` at 740, so every width
 * between 760 and 1440 went unlooked at. Four routes were scrolling sideways in
 * there — the reports page by 230px at every phone width, the analysis workspace
 * by 400px from 950 to 1350 — and both projects passed throughout.
 *
 * These assert what a tier is for rather than what it looks like: the page fits
 * its viewport, you can still navigate, and the panes that fold have folded.
 */
const TIERS = { sm: 640, md: 900, lg: 1050 } as const;

/**
 * Just inside and just outside each tier, plus the testing matrix from
 * docs/design-system.md §10.2 — 375 / 768 / 1024 / 1440 are widths to verify at,
 * not widths to fold at.
 */
const WIDTHS = [375, 660, 768, 800, TIERS.md - 1, TIERS.md, 1000, 1024, TIERS.lg, 1100, 1440];

/** Each test sets its own viewport, so a second project would repeat it exactly. */
const onlyOnce = (testInfo: { project: { name: string } }) =>
  test.skip(testInfo.project.name !== "chromium", "sets its own viewports");

async function seed(page: Page) {
  const created = await page.request.post(`${apiUrl}/requirements`, {
    data: {
      title: "Responsive layout smoke",
      description:
        "Make assisted channel ordering available to eligible SMB customers, with eligibility checked before an order can start.",
    },
  });
  const requirement = (await created.json()) as { id: string; analysis_context_token: string };
  await page.request.post(`${apiUrl}/requirements/${requirement.id}/analysis`, {
    data: { context_token: requirement.analysis_context_token, force: false },
  });
  return requirement.id;
}

async function signIn(page: Page) {
  await page.goto("/login?returnTo=%2F");
  const start = page.getByRole("button", { name: "Continue to workspace" });
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page.getByRole("heading", { name: "Requirements", exact: true })).toBeVisible();
}

/**
 * Measure the page, not the splash. Every route shows "Signing you in" first,
 * and a splash fits any viewport, so measuring without this asserts nothing.
 */
async function settled(page: Page) {
  await expect(page.locator('.loading-screen, [data-state="loading"]')).toHaveCount(0);
  await expect(page.locator(".app-topbar")).toBeVisible();
  await page.waitForLoadState("networkidle").catch(() => undefined);
}

async function documentFits(page: Page, width: number, route: string) {
  await settled(page);
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth), {
      message: `${route} should fit ${width}px without scrolling sideways`,
    })
    .toBeLessThanOrEqual(width);
}

test("every route fits its viewport across the tiers", async ({ page }, testInfo) => {
  onlyOnce(testInfo);
  // Eleven widths across seven routes: seventy-seven page loads, which is more
  // than the default budget allows for.
  test.slow();
  const id = await seed(page);
  await signIn(page);

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 1000 });
    for (const route of ["/", "/requirements/new", `/requirements/${id}/capture`,
      `/requirements/${id}/clarify`, `/requirements/${id}/breakdown`, "/documents", "/reports"]) {
      await page.goto(route);
      await documentFits(page, width, route);
      if (route === "/documents" && [375, 1440].includes(width)) {
        await page.screenshot({ path: testInfo.outputPath(`catalogue-${width}.png`), fullPage: true });
      }
    }
  }
});

test("navigation survives every tier, and the panes fold where they should", async ({ page }, testInfo) => {
  onlyOnce(testInfo);
  const id = await seed(page);
  await signIn(page);
  const sidebar = page.locator(".app-sidebar");
  const navButton = page.getByRole("button", { name: "Open navigation" });
  const rail = page.locator(".stage-rail");

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
    await settled(page);
    // There is one navigation now, and it is always reachable: the rail at md and
    // above, the same list behind the header button below it.
    const reachable = (await sidebar.isVisible()) || (await navButton.isVisible());
    expect(reachable, `no navigation is visible at ${width}px`).toBe(true);
    // The sidebar is the md tier's defining fold, and the button is its inverse:
    // exactly one of the two is on screen at any width.
    expect(await sidebar.isVisible(), `sidebar visibility at ${width}px`).toBe(width >= TIERS.md);
    expect(await navButton.isVisible(), `nav button visibility at ${width}px`).toBe(width < TIERS.md);

    await page.goto(`/requirements/${id}/clarify`);
    await settled(page);
    // The stage rail is present on every stage and at every width — that is what
    // "persistent" means. What changes is its shape.
    await expect(rail).toBeVisible();
    const [railBox, workspaceBox] = await Promise.all([
      rail.boundingBox(),
      page.locator(".workspace-body").boundingBox(),
    ]);
    // At lg and above the rail is the column beside the workspace; below it, a
    // scrolling row above it.
    const sideBySide = railBox!.x + railBox!.width <= workspaceBox!.x + 1;
    expect(sideBySide, `stage rail beside the workspace at ${width}px`).toBe(width >= TIERS.lg);

    // Source is a panel on every stage, at every width (ux-plan.md §4).
    await expect(page.getByRole("button", { name: "Source document" })).toBeVisible();
  }
});

test("the stage rail shows six steps and never wraps", async ({ page }, testInfo) => {
  onlyOnce(testInfo);
  const id = await seed(page);
  await signIn(page);
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(`/requirements/${id}/capture`);
    await settled(page);
    const steps = page.locator(".stage-rail ol > li");
    // Six. Review & approve is step 6, not a button in a page header
    // (ux-plan.md §3.2).
    await expect(steps).toHaveCount(6);
    const tops = await steps.evaluateAll((items) =>
      items.map((item) => Math.round(item.getBoundingClientRect().top)));
    // A column at lg and above, one scrolling row below it — and never the thing
    // it used to be, a five-column grid wrapping onto a second line.
    expect(new Set(tops).size, `stage rail rows at ${width}px`).toBe(width >= TIERS.lg ? 6 : 1);
  }
});

/**
 * WCAG 2.2 2.4.11, and the one docs/ux-plan.md §3.11 flags as unverified: the
 * fixed bar and any sticky rail can cover the element a keyboard just moved to.
 * Tab from the top of the document to the end of the chrome and check that what
 * has focus is somewhere a person can see it.
 */
test("focus is never hidden under the fixed header", async ({ page }, testInfo) => {
  onlyOnce(testInfo);
  const id = await seed(page);
  await signIn(page);
  for (const width of [375, TIERS.md, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of ["/", `/requirements/${id}/clarify`]) {
      await page.goto(route);
      await settled(page);
      await page.evaluate(() => document.body.focus());
      for (let stop = 0; stop < 25; stop += 1) {
        await page.keyboard.press("Tab");
        const hidden = await page.evaluate(() => {
          const active = document.activeElement as HTMLElement | null;
          if (!active || active === document.body) return null;
          const box = active.getBoundingClientRect();
          if (box.width === 0 && box.height === 0) return null;
          const header = document.querySelector(".app-topbar")?.getBoundingClientRect();
          // The skip link deliberately sits over the header; everything else
          // must clear it.
          if (active.classList.contains("skip-link")) return null;
          const underHeader = header && box.top < header.bottom && box.bottom > header.top
            && box.left < header.right && box.right > header.left
            && !active.closest(".app-topbar");
          const offscreen = box.bottom < 0 || box.top > window.innerHeight;
          return underHeader || offscreen
            ? `${active.tagName}.${active.className.toString().split(" ")[0]} top=${Math.round(box.top)}`
            : null;
        });
        expect(hidden, `focus obscured at ${width}px on ${route}`).toBeNull();
      }
    }
  }
});

test("the header never overlaps itself", async ({ page }, testInfo) => {
  onlyOnce(testInfo);
  await signIn(page);
  // Narrower than the sm tier too: the brand used to sit under the bell there.
  for (const width of [360, 480, ...WIDTHS]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await settled(page);
    const overlaps = await page.evaluate(() => {
      const parts = [".brand-lockup", ".notification-center", ".actor-menu", ".header-action"]
        .map((selector) => ({ selector, el: document.querySelector(selector) }))
        .filter((part) => part.el && getComputedStyle(part.el).display !== "none")
        .map((part) => ({ selector: part.selector, box: part.el!.getBoundingClientRect() }))
        .filter((part) => part.box.width > 0);
      const found: string[] = [];
      for (let i = 0; i < parts.length; i += 1) {
        for (let j = i + 1; j < parts.length; j += 1) {
          const a = parts[i]!.box, b = parts[j]!.box;
          const sameRow = a.top < b.bottom && b.top < a.bottom;
          if (sameRow && a.left < b.right && b.left < a.right) {
            found.push(`${parts[i]!.selector} over ${parts[j]!.selector}`);
          }
        }
      }
      return found;
    });
    expect(overlaps, `header at ${width}px`).toEqual([]);
    // And navigation is still reachable, on every one of those widths.
    const reachable = (await page.locator(".app-sidebar").isVisible())
      || (await page.getByRole("button", { name: "Open navigation" }).isVisible());
    expect(reachable, `no navigation is visible at ${width}px`).toBe(true);
  }
});
