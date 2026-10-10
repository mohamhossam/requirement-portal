import { baseUrl } from "./client";
import { isAbortedRequest } from "./errors";
import type { components } from "./schema";

export type ClientErrorKind = components["schemas"]["ClientErrorReport"]["kind"];

const reported = new Set<ClientErrorKind>();

/**
 * Tells operators that this browser hit a failure (`POST /client-errors`), which
 * otherwise only its console would see. It sends the kind alone: never a message
 * or stack, which could carry what the person was working on.
 *
 * Once per kind per page load, so a crash loop cannot flood the API. It goes
 * around the signed-in session on purpose: a report needs no token, and an
 * identity switch must not cancel it. `keepalive` lets it finish while the page
 * unloads, and a report that fails is dropped: there is nobody to tell.
 */
export function reportClientError(kind: ClientErrorKind): void {
  if (reported.has(kind)) return;
  reported.add(kind);
  void fetch(`${baseUrl}/client-errors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind }),
    keepalive: true,
  }).catch(() => undefined);
}

/**
 * Reports script errors and promise rejections nothing handled. A request
 * abandoned on purpose (`request_aborted`) is not a failure, so it is not reported.
 */
export function reportUncaughtErrors(target: Window = window): void {
  target.addEventListener("error", () => reportClientError("uncaught_error"));
  target.addEventListener("unhandledrejection", (event) => {
    if (!isAbortedRequest(event.reason)) reportClientError("unhandled_rejection");
  });
}
