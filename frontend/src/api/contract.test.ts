import { afterEach, beforeEach, expect, it, vi } from "vitest";

import openapi from "../../openapi.json";
import { api } from "./client";
import { knowledgeApi } from "./knowledge";

/**
 * The hand-written client may only call operations the API defines.
 *
 * `client.ts` builds every path by hand, so a renamed route or a wrong verb
 * would only surface at runtime. This calls every client function with a
 * stand-in argument, records each request it makes, and checks the method and
 * path against the committed OpenAPI contract (`openapi.json`, itself pinned
 * to the running API by `tests/unit/test_openapi_snapshot.py`).
 */

type Operation = { method: string; pattern: RegExp; template: string };

const operations: Operation[] = Object.entries(openapi.paths).flatMap(([template, item]) =>
  Object.keys(item).map((method) => ({
    method: method.toUpperCase(),
    template,
    pattern: new RegExp(`^${template.replace(/\{[^}]+\}/g, "[^/]+")}$`),
  })),
);

/**
 * Stands in for any argument: every property is itself, it converts to "x" in
 * paths and JSON, and it is truthy, so each function takes its main path.
 */
const anything: unknown = new Proxy(function stand() {}, {
  get(_target, key) {
    if (key === Symbol.toPrimitive || key === "toJSON" || key === "toString") return () => "x";
    if (key === "then") return undefined;
    if (key === Symbol.iterator) return function* single() { yield anything; };
    if (key === "length") return 1;
    return anything;
  },
  apply: () => anything,
});

const requests: { method: string; path: string }[] = [];

beforeEach(() => {
  requests.length = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = new URL(String(input));
    requests.push({
      method: (init?.method ?? "GET").toUpperCase(),
      path: url.pathname.replace(/^\/api/, ""),
    });
    return Promise.resolve(
      new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }),
    );
  });
  // Downloads end in an object URL, which jsdom does not provide.
  URL.createObjectURL = () => "blob:x";
  URL.revokeObjectURL = () => undefined;
});

afterEach(() => vi.restoreAllMocks());

const clients: [string, Record<string, unknown>][] = [
  ["api", api],
  ["knowledgeApi", knowledgeApi],
];

/** Functions whose literal argument is a path segment, called with each value. */
const literalArguments: Record<string, unknown[][]> = {
  "api.controlLibrary": [[anything, "retry"], [anything, "cancellation"]],
};

const functions = clients.flatMap(([owner, client]) =>
  Object.entries(client)
    .filter((entry): entry is [string, (...args: unknown[]) => unknown] =>
      typeof entry[1] === "function")
    .map(([name, call]) => ({ name: `${owner}.${name}`, call })),
);

const standIn = (call: (...args: unknown[]) => unknown) =>
  Array.from({ length: Math.max(call.length, 6) }, () => anything);

it("covers a meaningful share of the client", () => {
  expect(functions.length).toBeGreaterThan(140);
});

it.each(functions)("$name calls only operations the API defines", async ({ name, call }) => {
  for (const args of literalArguments[name] ?? [standIn(call)]) {
    try {
      await call(...args);
    } catch {
      // The stand-in response is not a real payload; only the request matters here.
    }
  }

  expect(requests.length).toBeGreaterThan(0);
  for (const request of requests) {
    const matched = operations.some(
      (operation) => operation.method === request.method && operation.pattern.test(request.path),
    );
    expect(matched, `${request.method} ${request.path} is not in openapi.json`).toBe(true);
  }
});
