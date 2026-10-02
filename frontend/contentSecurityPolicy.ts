import { createHash } from "node:crypto";
import type { Plugin } from "vite";

/**
 * Content-Security-Policy for the built app, delivered as a `<meta>` tag so it
 * travels with the static files whatever serves them.
 *
 * A meta policy cannot carry `frame-ancestors` or reporting; a server that
 * hosts the app should add those as headers. Development builds are left
 * alone because Vite's dev server relies on inline scripts for hot reload.
 */

export type PolicySources = {
  /** `VITE_API_BASE`; an absolute URL adds its origin to `connect-src`. */
  apiBase?: string;
  /** Space-separated OIDC issuer origins (`CSP_IDENTITY_ORIGINS`). */
  identityOrigins?: string;
};

const INLINE_SCRIPT = /<script>([\s\S]*?)<\/script>/g;

export function inlineScriptHashes(html: string): string[] {
  return [...html.matchAll(INLINE_SCRIPT)].map((match) => {
    // Browsers hash the script as parsed, and HTML parsing turns CRLF and CR
    // into LF. Hashing the raw text breaks on a Windows (CRLF) checkout.
    const parsed = (match[1] ?? "").replace(/\r\n?/g, "\n");
    return `'sha256-${createHash("sha256").update(parsed, "utf8").digest("base64")}'`;
  });
}

function origin(value: string, variable: string): string {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`${variable} must contain absolute origins; got ${JSON.stringify(value)}.`);
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") {
    throw new Error(`${variable} must use http or https; got ${JSON.stringify(value)}.`);
  }
  if (url.pathname !== "/" || url.search || url.hash) {
    throw new Error(`${variable} must list origins without a path; got ${JSON.stringify(value)}.`);
  }
  return url.origin;
}

export function buildPolicy(html: string, sources: PolicySources): string {
  const identity = (sources.identityOrigins ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .map((value) => origin(value, "CSP_IDENTITY_ORIGINS"));
  const api = /^https?:\/\//.test(sources.apiBase ?? "")
    ? [new URL(sources.apiBase as string).origin]
    : [];
  const directives: [string, string[]][] = [
    ["default-src", ["'self'"]],
    ["script-src", ["'self'", ...inlineScriptHashes(html)]],
    ["style-src", ["'self'"]],
    // Evidence previews arrive as data: URLs; protected assets as blob: URLs.
    ["img-src", ["'self'", "data:", "blob:"]],
    ["font-src", ["'self'", "data:"]],
    ["connect-src", ["'self'", ...api, ...identity]],
    // The PDF original is fetched with the bearer token and framed as a blob:
    // URL; an iframe cannot send that header, so a same-origin URL would not
    // authenticate. Only this origin can mint its blob: URLs, and a framed blob
    // inherits this policy, so it cannot run script. OIDC silent renewal runs
    // in a hidden iframe on the issuer.
    ["frame-src", ["blob:", ...identity]],
    ["form-action", ["'self'", ...identity]],
    ["object-src", ["'none'"]],
    ["base-uri", ["'self'"]],
  ];
  return directives.map(([name, values]) => `${name} ${[...new Set(values)].join(" ")}`).join("; ");
}

export function contentSecurityPolicy(sources: PolicySources): Plugin {
  return {
    name: "content-security-policy",
    apply: "build",
    transformIndexHtml: {
      order: "post",
      handler(html) {
        const tag = `<meta http-equiv="Content-Security-Policy" content="${buildPolicy(html, sources)}" />`;
        // After the charset declaration and before any script the policy governs.
        const charset = /<meta charset="[^"]*"\s*\/?>/i;
        if (!charset.test(html)) throw new Error("index.html needs a <meta charset> declaration.");
        return html.replace(charset, (declaration) => `${declaration}\n    ${tag}`);
      },
    },
  };
}
