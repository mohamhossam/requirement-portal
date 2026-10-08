import type { AiJobStartInput } from "../../api/client";
import { ApiError } from "../../api/errors";

// A request whose outcome is unknown may have started the job: the network failed
// (status 0) or the server failed after possibly committing (5xx).
function outcomeUnknown(error: unknown) {
  return error instanceof ApiError && (error.status === 0 || error.status >= 500);
}

/**
 * One Idempotency-Key per start input while its last attempt's outcome is unknown,
 * so trying the same thing again replays that attempt instead of starting a second job.
 */
export function createStartKeys() {
  const keys = new Map<string, string>();
  return {
    keyFor(input: AiJobStartInput) {
      const id = JSON.stringify(input);
      const key = keys.get(id) ?? crypto.randomUUID();
      keys.set(id, key);
      return key;
    },
    // After a success or a refusal (4xx) the next attempt is a new request.
    settle(input: AiJobStartInput, error?: unknown) {
      if (error !== undefined && outcomeUnknown(error)) return;
      keys.delete(JSON.stringify(input));
    },
  };
}

export type StartKeys = ReturnType<typeof createStartKeys>;
