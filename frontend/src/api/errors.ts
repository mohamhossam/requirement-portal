/**
 * The code of a request abandoned on purpose (status 0): the signed-in identity
 * changed, or its caller stopped waiting, as a query does when nobody shows it.
 */
export const ABORTED_REQUEST = "request_aborted";

/** The code of a request the server did not answer in time (status 0). */
export const REQUEST_TIMEOUT = "request_timeout";

export function isAbortedRequest(error: unknown): boolean {
  return error instanceof ApiError && error.code === ABORTED_REQUEST;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
    readonly code?: string,
    readonly correlationId?: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

type ValidationIssue = {
  loc?: Array<string | number>;
  msg?: string;
};

export function normalizeErrorDetail(payload: unknown, fallback: string): string {
  if (typeof payload !== "object" || payload === null) {
    return fallback;
  }
  if ("message" in payload && typeof payload.message === "string" && payload.message.trim()) {
    return payload.message;
  }
  if (!("detail" in payload)) return fallback;
  const detail = (payload as { detail: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item: ValidationIssue) => {
        if (typeof item?.msg !== "string") return null;
        const location = item.loc?.slice(1).join(" → ");
        return location ? `${location}: ${item.msg}` : item.msg;
      })
      .filter((item): item is string => item !== null);
    if (messages.length) return messages.join(". ");
  }
  return fallback;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

/**
 * The API's correlation ID for a failed request, which a person can quote and an
 * operator can find in the logs. Only answers from the API carry one.
 */
export function errorReference(error: unknown): string | null {
  return error instanceof ApiError && error.correlationId ? error.correlationId : null;
}
