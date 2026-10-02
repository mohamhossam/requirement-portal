import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import { buildPolicy } from "../../contentSecurityPolicy";

const THEME_SCRIPT = "\n  (function () { document.documentElement.dataset.x = '1'; })();\n";
const HTML = `<html><head><script>${THEME_SCRIPT}</script><script type="module" src="/assets/index.js"></script></head></html>`;

function directive(policy: string, name: string): string[] {
  const found = policy.split("; ").find((item) => item.startsWith(`${name} `));
  return found ? found.split(" ").slice(1) : [];
}

describe("buildPolicy", () => {
  it("allows only same-origin scripts plus the exact inline theme script", () => {
    const hash = createHash("sha256").update(THEME_SCRIPT, "utf8").digest("base64");

    expect(directive(buildPolicy(HTML, {}), "script-src")).toEqual(["'self'", `'sha256-${hash}'`]);
  });

  it("hashes an inline script as the browser parses it, whatever the line endings", () => {
    const crlf = HTML.replace(/\n/g, "\r\n");

    expect(directive(buildPolicy(crlf, {}), "script-src")).toEqual(
      directive(buildPolicy(HTML, {}), "script-src"),
    );
  });

  it("denies plugins, foreign frames and foreign base URLs by default", () => {
    const policy = buildPolicy(HTML, {});

    expect(directive(policy, "object-src")).toEqual(["'none'"]);
    // Only the app's own blob: URLs, which carry the authenticated PDF preview.
    expect(directive(policy, "frame-src")).toEqual(["blob:"]);
    expect(directive(policy, "base-uri")).toEqual(["'self'"]);
    expect(directive(policy, "connect-src")).toEqual(["'self'"]);
  });

  it("admits data and blob images used by evidence previews", () => {
    expect(directive(buildPolicy(HTML, {}), "img-src")).toEqual(["'self'", "data:", "blob:"]);
  });

  it("adds an absolute API origin but not a relative prefix", () => {
    expect(directive(buildPolicy(HTML, { apiBase: "/api" }), "connect-src")).toEqual(["'self'"]);
    expect(
      directive(buildPolicy(HTML, { apiBase: "https://api.example.test/v1" }), "connect-src"),
    ).toEqual(["'self'", "https://api.example.test"]);
  });

  it("lets the configured identity issuer serve tokens, silent renewal and sign-in forms", () => {
    const policy = buildPolicy(HTML, { identityOrigins: " https://login.example.test " });

    expect(directive(policy, "connect-src")).toContain("https://login.example.test");
    expect(directive(policy, "frame-src")).toEqual(["blob:", "https://login.example.test"]);
    expect(directive(policy, "form-action")).toEqual(["'self'", "https://login.example.test"]);
  });

  it.each(["login.example.test", "https://login.example.test/realms/app", "ftp://login.example.test"])(
    "rejects %s as an identity origin",
    (value) => {
      expect(() => buildPolicy(HTML, { identityOrigins: value })).toThrow(/CSP_IDENTITY_ORIGINS/);
    },
  );
});
