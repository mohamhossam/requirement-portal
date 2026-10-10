import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Fresh modules, so each test starts with nothing reported yet. The errors module
 * comes from the same fresh graph, so `instanceof ApiError` still matches.
 */
async function reporter() {
  vi.resetModules();
  return { ...(await import("./clientErrors")), ...(await import("./errors")) };
}

describe("client error reports", () => {
  let sent: { url: string; init: RequestInit | undefined }[];

  beforeEach(() => {
    sent = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      sent.push({ url: String(input), init });
      return Promise.resolve(new Response(null, { status: 204 }));
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("send the kind alone, without a token, and outlive the page", async () => {
    const { reportClientError } = await reporter();

    reportClientError("render");

    expect(sent).toHaveLength(1);
    expect(sent[0]?.url).toMatch(/\/api\/client-errors$/);
    expect(sent[0]?.init).toMatchObject({ method: "POST", keepalive: true, body: '{"kind":"render"}' });
    expect(new Headers(sent[0]?.init?.headers).has("Authorization")).toBe(false);
  });

  it("send each kind once per page load, so a crash loop cannot flood the API", async () => {
    const { reportClientError } = await reporter();

    reportClientError("render");
    reportClientError("render");
    reportClientError("chunk_load");

    expect(sent.map((item) => item.init?.body)).toEqual(['{"kind":"render"}', '{"kind":"chunk_load"}']);
  });

  it("swallow a report that fails, since there is nobody to tell", async () => {
    vi.mocked(globalThis.fetch).mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const { reportClientError } = await reporter();

    expect(() => reportClientError("render")).not.toThrow();
    await Promise.resolve();
  });

  it("cover uncaught errors and rejections, but not a request abandoned on purpose", async () => {
    const { reportUncaughtErrors, ApiError, ABORTED_REQUEST } = await reporter();
    const target = new EventTarget() as Window;
    reportUncaughtErrors(target);
    const rejection = (reason: unknown) =>
      Object.assign(new Event("unhandledrejection"), { reason }) as PromiseRejectionEvent;

    target.dispatchEvent(rejection(new ApiError(0, "Cancelled.", ABORTED_REQUEST)));
    expect(sent).toHaveLength(0);

    target.dispatchEvent(new Event("error"));
    target.dispatchEvent(rejection(new Error("boom")));

    expect(sent.map((item) => item.init?.body)).toEqual([
      '{"kind":"uncaught_error"}',
      '{"kind":"unhandled_rejection"}',
    ]);
  });
});
