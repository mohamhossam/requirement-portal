import { describe, expect, it } from "vitest";

import { ABORTED_REQUEST, ApiError } from "../api/errors";
import { mutationErrorToast } from "./mutationErrors";

describe("mutation error notices", () => {
  it("names the action the person was taking", () => {
    const notice = mutationErrorToast(new ApiError(500, "Upstream exploded."), {
      action: "Approving the Epic",
    });
    expect(notice).toMatchObject({
      tone: "error",
      title: "Approving the Epic failed",
      message: "Upstream exploded.",
    });
  });

  it("still reports an action that did not declare itself", () => {
    expect(mutationErrorToast(new ApiError(500, "Upstream exploded."))).toMatchObject({
      title: "That action could not be completed",
      message: "Upstream exploded.",
    });
  });

  it("stays silent on a version conflict, which the editors reconcile in place", () => {
    expect(mutationErrorToast(new ApiError(409, "Stale version."), { action: "Saving the Epic" }))
      .toBeNull();
  });

  it("stays silent on an expired session, which the header already offers to renew", () => {
    expect(mutationErrorToast(new ApiError(401, "Token expired."))).toBeNull();
  });

  it("honours a mutation that reports its own outcome", () => {
    expect(mutationErrorToast(new ApiError(500, "Nope."), { toastOnError: false })).toBeNull();
  });

  it("reports a network failure, which carries no status", () => {
    expect(mutationErrorToast(new ApiError(0, "The API is unavailable."), { action: "Saving" }))
      .toMatchObject({ tone: "error", message: "The API is unavailable." });
  });

  it("stays silent on a request abandoned because the person changed identity", () => {
    expect(mutationErrorToast(new ApiError(0, "Cancelled.", ABORTED_REQUEST), { action: "Saving" }))
      .toBeNull();
  });

  it("copes with something thrown that is not an ApiError", () => {
    expect(mutationErrorToast(new TypeError("boom"))).toMatchObject({ message: "boom" });
    expect(mutationErrorToast("a bare string")).toMatchObject({
      message: "Something went wrong. Please try again.",
    });
  });

  it("collapses repeats of one action onto a single notice", () => {
    const a = mutationErrorToast(new ApiError(500, "one"), { action: "Approving the Epic" });
    const b = mutationErrorToast(new ApiError(503, "two"), { action: "Approving the Epic" });
    const other = mutationErrorToast(new ApiError(500, "three"), { action: "Saving the Epic" });
    expect(a?.key).toBe(b?.key);
    expect(a?.key).not.toBe(other?.key);
  });
});
