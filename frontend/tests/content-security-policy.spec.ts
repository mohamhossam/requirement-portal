import { expect, test } from "@playwright/test";

const apiUrl = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;

// Full Chromium, not the default headless shell: the shell has no PDF viewer
// and downloads a framed PDF instead of rendering it as a person's browser would.
test.use({ channel: "chromium" });

/**
 * The built app ships a Content-Security-Policy (contentSecurityPolicy.ts). A
 * policy that is too strict fails silently in production — a blocked script,
 * font or image just does not appear — so every screen here must load without
 * a single violation.
 */
test("the built app loads every screen without a policy violation", async ({ page }) => {
  const violations: string[] = [];
  await page.addInitScript(() => {
    localStorage.setItem("requirement-ai-theme", "dark");
    document.addEventListener("securitypolicyviolation", (event) => {
      console.error(`CSP violation: ${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  page.on("console", (message) => {
    if (/Content Security Policy|CSP violation/i.test(message.text())) violations.push(message.text());
  });

  await page.goto("/");
  const policy = await page
    .locator('meta[http-equiv="Content-Security-Policy"]')
    .getAttribute("content");
  expect(policy).toContain("object-src 'none'");
  // The inline theme script is admitted by hash, so the stored choice applies.
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  const created = await page.request.post(`${apiUrl}/requirements`, {
    data: { title: "Policy smoke", description: "Load every workspace stage under the policy." },
  });
  expect(created.ok()).toBeTruthy();
  const { id } = (await created.json()) as { id: string };
  const workspace = ["capture", "clarify", "knowledge", "confirm", "breakdown", "revisions", "review"];

  for (const path of [
    "/",
    "/requirements/new",
    "/documents",
    "/documents/library",
    "/architecture-knowledge",
    "/activity",
    "/reports",
    ...workspace.map((view) => `/requirements/${id}/${view}`),
  ]) {
    await page.goto(path);
    await expect(page.locator("main")).toBeVisible();
    await page.waitForLoadState("networkidle");
  }

  expect(violations).toEqual([]);
});

/** A one-page PDF with a text line, its cross-reference offsets computed. */
function onePagePdf(text: string): Buffer {
  const content = `BT /F1 18 Tf 72 720 Td (${text}) Tj ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let body = "%PDF-1.4\n";
  const offsets = objects.map((object, index) => {
    const offset = body.length;
    body += `${index + 1} 0 obj\n${object}\nendobj\n`;
    return offset;
  });
  const xref = body.length;
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  body += offsets.map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`).join("");
  body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body, "latin1");
}

/**
 * The PDF original is fetched with the caller's credentials and framed from a
 * blob: URL, so `frame-src` has to admit blob: — and nothing broader.
 */
test("a PDF source document previews its original under the policy", async ({ page }) => {
  const violations: string[] = [];
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (event) => {
      console.error(`CSP violation: ${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  page.on("console", (message) => {
    if (/Content Security Policy|CSP violation/i.test(message.text())) violations.push(message.text());
  });

  const created = await page.request.post(`${apiUrl}/requirements`, {
    data: { title: "PDF policy smoke", description: "Preview a PDF original under the policy." },
  });
  expect(created.ok()).toBeTruthy();
  const { id } = (await created.json()) as { id: string };
  const uploaded = await page.request.post(`${apiUrl}/requirements/${id}/attachments`, {
    multipart: {
      include_in_analysis: "true",
      file: { name: "policy-original.pdf", mimeType: "application/pdf", buffer: onePagePdf("Policy original") },
    },
  });
  expect(uploaded.ok()).toBeTruthy();
  const source = (await uploaded.json()) as { id: string };

  await page.goto(`/documents/${source.id}`);
  await expect(page.getByTitle("Preview of policy-original.pdf")).toHaveAttribute("src", /^blob:/);
  // A refused frame never commits the blob document, and the viewer inside
  // it only loads once the PDF is admitted.
  await expect.poll(() => page.frames().map((frame) => frame.url().split(":")[0])).toEqual(
    expect.arrayContaining(["blob", "chrome-extension"]),
  );
  await page.waitForLoadState("networkidle");

  expect(violations).toEqual([]);
});
