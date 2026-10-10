import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import {
  api,
  configureAuthentication,
  configureAuthenticationHeaders,
  replaceAuthenticationHeaders,
  DOWNLOAD_URL_LIFETIME_MS,
} from "./client";
import { ABORTED_REQUEST, ApiError, REQUEST_TIMEOUT } from "./errors";

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  configureAuthentication(() => ({}));
});
afterAll(() => server.close());

it("rejects a document body completed after the credential session changes", async () => {
  let finishBody!: (value: Blob) => void;
  let bodyStarted!: () => void;
  const started = new Promise<void>((resolve) => { bodyStarted = resolve; });
  const response = new Response(null, { status: 200 });
  vi.spyOn(response, "blob").mockImplementation(() => {
    bodyStarted();
    return new Promise<Blob>((resolve) => { finishBody = resolve; });
  });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
  try {
    configureAuthentication(() => ({ Authorization: "Bearer first" }));
    const request = api.getDocumentPdf("document-1");
    await started;
    configureAuthenticationHeaders(() => ({ Authorization: "Bearer second" }));
    finishBody(new Blob(["private document"]));
    await expect(request).rejects.toMatchObject({ status: 0, code: ABORTED_REQUEST });
  } finally {
    fetchMock.mockRestore();
  }
});

it("discards a JSON answer that arrives after the identity changed, as an aborted request", async () => {
  let finishBody!: (value: unknown) => void;
  let bodyStarted!: () => void;
  const started = new Promise<void>((resolve) => { bodyStarted = resolve; });
  const response = new Response(null, { status: 200 });
  vi.spyOn(response, "json").mockImplementation(() => {
    bodyStarted();
    return new Promise((resolve) => { finishBody = resolve; });
  });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
  try {
    configureAuthentication(() => ({ "X-Fake-Actor-Id": "fake-owner" }));
    const request = api.getCurrentActor();
    await started;
    configureAuthenticationHeaders(() => ({ "X-Fake-Actor-Id": "fake-reviewer" }));
    finishBody({ id: "fake-owner", display_name: "Owner", email: null });
    await expect(request).rejects.toEqual(expect.objectContaining({ status: 0, code: ABORTED_REQUEST }));
  } finally {
    fetchMock.mockRestore();
  }
});

it("lets a request in flight finish when only the token is renewed", async () => {
  let finishBody!: (value: unknown) => void;
  let bodyStarted!: () => void;
  const started = new Promise<void>((resolve) => { bodyStarted = resolve; });
  const response = new Response(null, { status: 200 });
  vi.spyOn(response, "json").mockImplementation(() => {
    bodyStarted();
    return new Promise((resolve) => { finishBody = resolve; });
  });
  const sent: string[] = [];
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((_url, init) => {
    sent.push(new Headers(init?.headers).get("authorization") ?? "");
    return Promise.resolve(response);
  });
  try {
    configureAuthentication(() => ({ Authorization: "Bearer first" }));
    const request = api.getCurrentActor();
    await started;
    replaceAuthenticationHeaders(() => ({ Authorization: "Bearer renewed" }));
    finishBody({ id: "owner", display_name: "Owner", email: null });
    await expect(request).resolves.toMatchObject({ id: "owner" });
    void api.getCurrentActor().catch(() => undefined);
    expect(sent).toEqual(["Bearer first", "Bearer renewed"]);
  } finally {
    fetchMock.mockRestore();
  }
});

it("reports a network failure as status 0 without the aborted code", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
  try {
    const failure = await api.getCurrentActor().catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ status: 0, detail: "Failed to fetch", code: undefined });
  } finally {
    fetchMock.mockRestore();
  }
});

describe("API client", () => {
  it("starts durable AI work with an idempotency key", async () => {
    let key = "";
    let body: unknown;
    server.use(
      http.post("http://localhost/api/requirements/r-1/ai-jobs", async ({ request }) => {
        key = request.headers.get("idempotency-key") ?? "";
        body = await request.json();
        return HttpResponse.json({ id: "job-1" }, { status: 202 });
      }),
    );

    await api.startAiJob(
      "r-1",
      { operation: "analyse_requirement", context_token: "analysis-context", force: true },
      "stable-action-1",
    );

    expect(key).toBe("stable-action-1");
    expect(body).toEqual({
      operation: "analyse_requirement",
      context_token: "analysis-context",
      force: true,
    });
  });

  it("encodes repeated workflow filters and pagination for the worklist", async () => {
    let query = "";
    server.use(
      http.get("http://localhost/api/requirements", ({ request }) => {
        query = new URL(request.url).search;
        return HttpResponse.json({ requirements: [] });
      }),
    );

    await api.listRequirements({
      q: "  coverage  ",
      workflowStatus: ["needs_answers", "stale"],
      sort: "title_asc",
      offset: 20,
      limit: 20,
      ownerId: "actor-1",
      assignedToMe: true,
    });

    const params = new URLSearchParams(query);
    expect(params.get("q")).toBe("coverage");
    expect(params.getAll("workflow_status")).toEqual(["needs_answers", "stale"]);
    expect(params.get("sort")).toBe("title_asc");
    expect(params.get("offset")).toBe("20");
    expect(params.get("owner_id")).toBe("actor-1");
    expect(params.get("assigned_to_me")).toBe("true");
  });

  it("injects authentication and reports a 401 without discarding caller state", async () => {
    const unauthorized = vi.fn();
    configureAuthentication(() => ({ Authorization: "Bearer token" }), unauthorized);
    let authorization = "";
    server.use(http.get("http://localhost/api/identity/me", ({ request }) => {
      authorization = request.headers.get("authorization") ?? "";
      return HttpResponse.json({ detail: "expired" }, { status: 401 });
    }));

    await expect(api.getCurrentActor()).rejects.toEqual(new ApiError(401, "expired"));
    expect(authorization).toBe("Bearer token");
    expect(unauthorized).toHaveBeenCalledOnce();
  });

  it("treats a missing derived artifact as a normal empty state", async () => {
    server.use(http.get("http://localhost/api/requirements/r-1/analysis", () => HttpResponse.json({ detail: "missing" }, { status: 404 })));
    await expect(api.getAnalysis("r-1")).resolves.toBeNull();
  });

  it("normalises FastAPI validation arrays", async () => {
    server.use(http.post("http://localhost/api/requirements", () => HttpResponse.json({ detail: [{ loc: ["body", "title"], msg: "Field required" }] }, { status: 422 })));
    await expect(api.createRequirement({ title: "", description: "D" })).rejects.toEqual(
      new ApiError(422, "title: Field required"),
    );
  });

  it("preserves mapped domain error detail", async () => {
    server.use(http.post("http://localhost/api/requirements/r-1/epic/approval", () => HttpResponse.json({
      code: "stale_epic_approval",
      message: "Epic is stale.",
      correlation_id: "request-1",
    }, { status: 409 })));
    await expect(api.approveEpic("r-1", 1, "fingerprint-1")).rejects.toEqual(
      new ApiError(409, "Epic is stale.", "stale_epic_approval", "request-1"),
    );
  });

  it("lets the browser set the multipart upload boundary", async () => {
    let contentType = "";
    server.use(
      http.post("http://localhost/api/requirements/r-1/attachments", ({ request }) => {
        contentType = request.headers.get("content-type") ?? "";
        return HttpResponse.json({ id: "document-1" });
      }),
    );

    await api.uploadRequirementDocument(
      "r-1",
      new File(["policy"], "policy.txt", { type: "text/plain" }),
    );

    expect(contentType).toMatch(/^multipart\/form-data; boundary=/);
  });

  it("downloads an authenticated export using the server filename", async () => {
    configureAuthentication(() => ({ Authorization: "Bearer export-token" }));
    const createObjectUrl = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:export");
    const revokeObjectUrl = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    let authorization = "";
    server.use(
      http.get(
        "http://localhost/api/requirements/r-1/revisions/7/export",
        ({ request }) => {
          authorization = request.headers.get("authorization") ?? "";
          return new HttpResponse("{}", {
            headers: {
              "Content-Type": "application/json",
              "Content-Disposition": 'attachment; filename="approved-v7.json"',
            },
          });
        },
      ),
    );

    vi.useFakeTimers({ shouldAdvanceTime: true, toFake: ["setTimeout", "clearTimeout"] });
    try {
      await api.exportBreakdownRevision("r-1", 7, "json");

      expect(authorization).toBe("Bearer export-token");
      expect(createObjectUrl).toHaveBeenCalledOnce();
      expect(click).toHaveBeenCalledOnce();
      // Kept alive past the click, so a browser that starts the download later still has it.
      expect(revokeObjectUrl).not.toHaveBeenCalled();
      vi.advanceTimersByTime(DOWNLOAD_URL_LIFETIME_MS);
      expect(revokeObjectUrl).toHaveBeenCalledWith("blob:export");
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("timeouts and cancellation", () => {
  /** A server that never answers: the request ends only when its signal aborts. */
  function hangingFetch() {
    return vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      }));
  }

  /** Hands out a timeout signal the test fires itself. */
  function controlledTimeout() {
    const timeout = new AbortController();
    const spy = vi.spyOn(AbortSignal, "timeout").mockReturnValue(timeout.signal);
    return { spy, fire: () => timeout.abort(new DOMException("Timed out", "TimeoutError")) };
  }

  afterEach(() => vi.restoreAllMocks());

  it("gives up on a JSON request after 30 seconds, as a timeout", async () => {
    const timeout = controlledTimeout();
    hangingFetch();

    const request = api.getRequirement("r-1");
    timeout.fire();

    expect(timeout.spy).toHaveBeenCalledWith(30_000);
    await expect(request).rejects.toMatchObject({ status: 0, code: REQUEST_TIMEOUT });
  });

  it("allows two minutes for uploads and document downloads", async () => {
    const timeout = controlledTimeout();
    hangingFetch();

    const upload = api.uploadRequirementDocument("r-1", new File(["policy"], "policy.txt"));
    const pdf = api.getDocumentPdf("document-1");
    timeout.fire();

    expect(timeout.spy.mock.calls).toEqual([[120_000], [120_000]]);
    await expect(upload).rejects.toMatchObject({ code: REQUEST_TIMEOUT });
    await expect(pdf).rejects.toMatchObject({ code: REQUEST_TIMEOUT });
  });

  it("passes a query's signal to fetch, and its abort is a silent cancellation", async () => {
    const fetchMock = hangingFetch();
    const query = new AbortController();

    const request = api.getRequirement("r-1", { signal: query.signal });
    query.abort();

    await expect(request).rejects.toMatchObject({ status: 0, code: ABORTED_REQUEST });
    const sent = fetchMock.mock.calls[0]?.[1]?.signal;
    expect(sent?.aborted).toBe(true);
  });

  it("works where the browser has no AbortSignal.any, as older Safari", async () => {
    const native = AbortSignal.any;
    Reflect.deleteProperty(AbortSignal, "any");
    try {
      expect(AbortSignal.any).toBeUndefined();
      const timeout = controlledTimeout();
      hangingFetch();
      const query = new AbortController();

      const timedOut = api.getRequirement("r-1");
      const cancelled = api.getRequirement("r-2", { signal: query.signal });
      query.abort();
      timeout.fire();

      await expect(cancelled).rejects.toMatchObject({ code: ABORTED_REQUEST });
      await expect(timedOut).rejects.toMatchObject({ code: REQUEST_TIMEOUT });
    } finally {
      AbortSignal.any = native;
    }
  });

  it("still reports a network failure as one", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    const failure = await api.getRequirement("r-1").catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ status: 0, code: undefined, detail: "Failed to fetch" });
  });
});
