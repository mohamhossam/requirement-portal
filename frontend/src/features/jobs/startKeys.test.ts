import { describe, expect, it } from "vitest";

import type { AiJobStartInput } from "../../api/client";
import { ABORTED_REQUEST, ApiError } from "../../api/errors";
import { createStartKeys } from "./startKeys";

const input = { operation: "generate_epic", context_token: "token", force: false } as AiJobStartInput;

describe("start keys", () => {
  it("replays the same key while the last attempt's outcome is unknown", () => {
    const keys = createStartKeys();
    const first = keys.keyFor(input);

    keys.settle(input, new ApiError(0, "Failed to fetch"));
    expect(keys.keyFor(input)).toBe(first);
    keys.settle(input, new ApiError(503, "Unavailable"));
    expect(keys.keyFor(input)).toBe(first);
  });

  it("keeps the key of a start abandoned when the identity changed, which may have reached the server", () => {
    const keys = createStartKeys();
    const first = keys.keyFor(input);

    keys.settle(input, new ApiError(0, "Cancelled.", ABORTED_REQUEST));

    expect(keys.keyFor(input)).toBe(first);
  });

  it("starts afresh after a success or a refusal", () => {
    const keys = createStartKeys();
    const first = keys.keyFor(input);
    keys.settle(input);
    const second = keys.keyFor(input);
    keys.settle(input, new ApiError(409, "Changed"));

    expect(second).not.toBe(first);
    expect(keys.keyFor(input)).not.toBe(second);
  });
});
