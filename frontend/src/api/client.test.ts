import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { api, configureAuthentication, configureAuthenticationHeaders } from "./client";
import { ApiError } from "./errors";

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
    await expect(request).rejects.toMatchObject({ name: "AbortError" });
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

  it("posts human clarification answers to the same requirement analysis", async () => {
    let body: unknown;
    server.use(
      http.post("http://localhost/api/requirements/r-1/analysis/clarifications", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ requirement_id: "r-1" });
      }),
    );

    await api.clarifyAnalysis(
      "r-1",
      [{ kind: "open_question", subject: "Who owns it?", answer: "Product" }],
      3,
    );

    expect(body).toEqual({
      answers: [{ kind: "open_question", subject: "Who owns it?", answer: "Product" }],
      expected_analysis_version: 3,
    });
  });

  it("posts stable clarification answers as one batch", async () => {
    let body: unknown;
    server.use(
      http.post(
        "http://localhost/api/requirements/r-1/analysis/question-resolutions",
        async ({ request }) => {
          body = await request.json();
          return HttpResponse.json({ requirement_id: "r-1" });
        },
      ),
    );

    await api.resolveClarificationQuestions("r-1", [
      { question_id: "question-1", answer: "Product", expected_version: 2 },
      { question_id: "question-2", answer: "Operations", expected_version: 1 },
    ]);

    expect(body).toEqual({
      answers: [
        { question_id: "question-1", answer: "Product", expected_version: 2 },
        { question_id: "question-2", answer: "Operations", expected_version: 1 },
      ],
    });
  });

  it("maps the whole requirement breakdown through one explicit action", async () => {
    let method = "";
    server.use(
      http.post("http://localhost/api/requirements/r-1/architecture-mapping", ({ request }) => {
        method = request.method;
        return HttpResponse.json({ requirement_id: "r-1", features: [] });
      }),
    );

    await api.mapArchitecture("r-1");

    expect(method).toBe("POST");
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
          return new HttpResponse(new Blob(["{}"]), {
            headers: {
              "Content-Type": "application/json",
              "Content-Disposition": 'attachment; filename="approved-v7.json"',
            },
          });
        },
      ),
    );

    await api.exportBreakdownRevision("r-1", 7, "json");

    expect(authorization).toBe("Bearer export-token");
    expect(createObjectUrl).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:export");
  });
});
