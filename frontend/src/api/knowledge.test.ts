import { describe, expect, it } from "vitest";

import { knowledgePortalUrl } from "./knowledge";

describe("knowledgePortalUrl", () => {
  it("defaults to the platform path when nothing is configured", () => {
    expect(knowledgePortalUrl(undefined)).toBe("/knowledge/");
  });

  it("uses the configured address, such as the portal's own host", () => {
    expect(knowledgePortalUrl(" https://knowledge.example.com/ ")).toBe("https://knowledge.example.com/");
  });

  it("is absent when configured empty, so no link to the portal is shown", () => {
    expect(knowledgePortalUrl("")).toBeNull();
    expect(knowledgePortalUrl("  ")).toBeNull();
  });
});
