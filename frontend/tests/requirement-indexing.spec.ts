import { expect, test } from "@playwright/test";
import path from "node:path";

const apiRoot = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;

test("background Requirement indexing reaches ready and exposes recovery", async ({ page }, testInfo) => {
  const narrow = testInfo.project.name.includes("responsive");
  if (narrow) await page.setViewportSize({ width: 390, height: 844 });
  const created = await page.request.post(`${apiRoot}/requirements`, {
    headers: { "X-Fake-Actor-Id": "fake-owner" },
    data: { title: `Indexed coverage ${Date.now()}`, description: "التغطية مطلوبة. Coverage is required before ordering." },
  });
  expect(created.status()).toBe(201);
  const requirement = await created.json() as { id: string };
  const indexUrl = `${apiRoot}/requirements/${requirement.id}/knowledge-index`;
  await expect.poll(async () => {
    const status = await page.request.get(indexUrl, { headers: { "X-Fake-Actor-Id": "fake-owner" } });
    expect(status.ok()).toBeTruthy();
    return (await status.json() as { state: string }).state;
  }).toBe("ready");

  // An explicit transport fixture exercises the rare terminal failure/recovery surface.
  let retried = false;
  await page.route(`**/requirements/${requirement.id}/knowledge-index`, route => route.fulfill({
    json: { state: retried ? "ready" : "failed", completed_chunks: 16, total_chunks: 25, retryable: !retried },
  }));
  await page.route(`**/requirements/${requirement.id}/knowledge-index/retry`, async route => {
    expect(route.request().method()).toBe("POST");
    retried = true;
    await route.fulfill({ json: { state: "ready", completed_chunks: 25, total_chunks: 25, retryable: false } });
  });
  await page.goto(`/requirements/${requirement.id}/knowledge`);
  const notice = page.getByRole("region", { name: "Knowledge preparation" });
  await expect(notice).toBeVisible();
  await expect(notice.getByText("16 of 25 sections prepared.")).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: path.resolve("../logs", `requirement-index-${narrow ? "mobile" : "desktop"}.png`), fullPage: true });
  await notice.getByRole("button", { name: "Retry knowledge preparation" }).click();
  await expect(notice).not.toBeVisible();
  expect(retried).toBeTruthy();
});
