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
