import { describe, expect, it } from "vitest";

import { safeAuthReturnPath } from "./returnPath";

describe("safeAuthReturnPath", () => {
  it("keeps a same-origin path with its query and fragment", () => {
    expect(safeAuthReturnPath("/requirements/req-1/clarify?tab=open#q-2")).toBe(
      "/requirements/req-1/clarify?tab=open#q-2",
    );
  });

  it("falls back to the worklist when nothing was requested", () => {
    expect(safeAuthReturnPath(null)).toBe("/");
    expect(safeAuthReturnPath(undefined)).toBe("/");
    expect(safeAuthReturnPath("")).toBe("/");
  });

  it("refuses another origin, so sign-in cannot be used as an open redirect", () => {
    expect(safeAuthReturnPath("https://evil.example/phish")).toBe("/");
    // Protocol-relative URLs resolve to another origin too.
    expect(safeAuthReturnPath("//evil.example/phish")).toBe("/");
  });

  it("refuses the auth routes themselves, which would loop the sign-in", () => {
    for (const path of ["/login", "/auth/callback", "/auth/silent-callback"]) {
      expect(safeAuthReturnPath(path)).toBe("/");
    }
  });

  it("normalises a relative candidate against the origin", () => {
    expect(safeAuthReturnPath("requirements/new")).toBe("/requirements/new");
  });
});
