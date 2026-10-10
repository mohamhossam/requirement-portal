import { afterEach, describe, expect, it, vi } from "vitest";

import { knowledgePortalRole, knowledgePortalUrl, runtimeValue } from "./knowledge";

describe("knowledgePortalUrl", () => {
  it("defaults to the platform path when nothing is configured", () => {
    expect(knowledgePortalUrl(undefined)).toBe("/knowledge/");
  });

  it("uses the configured address, such as the portal's own host", () => {
    expect(knowledgePortalUrl(" https://knowledge.example.com/ ")).toBe(
      "https://knowledge.example.com/",
    );
  });

  it("is absent when configured empty, so no link to the portal is shown", () => {
    expect(knowledgePortalUrl("")).toBeNull();
    expect(knowledgePortalUrl("  ")).toBeNull();
  });
});

describe("knowledgePortalRole", () => {
  it("defaults to the portal's knowledge_admin role", () => {
    expect(knowledgePortalRole(undefined)).toBe("knowledge_admin");
  });

  it("uses the configured role", () => {
    expect(knowledgePortalRole(" curators ")).toBe("curators");
  });

  it("is absent when configured empty, so everyone signed in sees the links", () => {
    expect(knowledgePortalRole("")).toBeNull();
  });
});

describe("values the web container renders at start", () => {
  function meta(name: string, content: string) {
    const tag = document.createElement("meta");
    tag.name = name;
    tag.content = content;
    document.head.append(tag);
  }

  afterEach(() => {
    document.head.querySelectorAll('meta[name^="knowledge-portal-"]').forEach((tag) => tag.remove());
    vi.resetModules();
  });

  it("are read from index.html, empty included, and absent without the tag", () => {
    meta("knowledge-portal-url", "");
    expect(runtimeValue("knowledge-portal-url")).toBe("");
    expect(runtimeValue("knowledge-portal-role")).toBeUndefined();
  });

  it("decide the portal's address and role over the build's", async () => {
    meta("knowledge-portal-url", "https://knowledge.example.com/");
    meta("knowledge-portal-role", "");
    vi.resetModules();

    const fresh = await import("./knowledge");

    expect(fresh.KNOWLEDGE_PORTAL_URL).toBe("https://knowledge.example.com/");
    // Rendered empty: everyone signed in sees the links.
    expect(fresh.KNOWLEDGE_ADMIN_ROLE).toBeNull();
  });
});
