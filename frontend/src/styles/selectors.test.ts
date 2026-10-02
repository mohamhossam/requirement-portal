import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * A selector is declared in one stylesheet (docs/ux-plan.md §5, Phase 0 step 2).
 *
 * There were 216 that were not. Three visual generations each redeclared the
 * rules of the one before, whole files of them existed only to override
 * 01-foundation.css, and index.css carried a warning that regrouping the imports
 * would change what renders. Phase 0.5 folded every selector into a single
 * declaration; this keeps it that way, so the import order stays inert.
 *
 * The same selector inside a different media query is a different declaration
 * — that is what a responsive rule is — and is allowed. tokens.css is exempt: it
 * holds only custom-property blocks, and `:root` there and in base.css do
 * different jobs.
 */
const SOURCE = join(process.cwd(), "src");
const TOKENS = join(SOURCE, "styles", "tokens.css");

function files(directory: string): string[] {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) return files(path);
    return name.endsWith(".css") ? [path] : [];
  });
}

/** Top-level commas only: `.row > :is(button, a)` is one selector. */
function splitSelectors(head: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let current = "";
  for (const char of head) {
    if (char === "(") depth += 1;
    if (char === ")") depth -= 1;
    if (char === "," && depth === 0) {
      parts.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  parts.push(current);
  return parts.map((part) => part.trim().replace(/\s+/g, " ")).filter(Boolean);
}

/** Every (at-rule context, selector) the stylesheet declares. */
function declarations(css: string): string[] {
  const out: string[] = [];
  const context: string[] = [];
  let head = "";
  for (const char of css.replace(/\/\*[\s\S]*?\*\//g, "")) {
    if (char === "{") {
      const trimmed = head.trim().replace(/\s+/g, " ");
      if (trimmed.startsWith("@")) {
        context.push(trimmed);
      } else {
        // Keyframe steps are not selectors.
        if (!context.some((at) => at.startsWith("@keyframes"))) {
          for (const selector of splitSelectors(trimmed)) out.push(`${context.join(" ")} ${selector}`.trim());
        }
        context.push("");
      }
      head = "";
    } else if (char === "}") {
      context.pop();
      head = "";
    } else if (char === ";") {
      head = "";
    } else {
      head += char;
    }
  }
  return out;
}

describe("selectors", () => {
  it("declares every selector in exactly one stylesheet", () => {
    const owners = new Map<string, Set<string>>();
    for (const path of files(SOURCE)) {
      if (path === TOKENS) continue;
      const name = relative(SOURCE, path);
      for (const key of declarations(readFileSync(path, "utf8"))) {
        owners.set(key, (owners.get(key) ?? new Set()).add(name));
      }
    }
    const shared = [...owners].filter(([, names]) => names.size > 1).map(([key, names]) => `${key} — ${[...names].sort().join(", ")}`);
    expect(shared).toEqual([]);
  });

  it("splits a selector list on top-level commas only", () => {
    expect(splitSelectors(".a > :is(button, a), .b")).toEqual([".a > :is(button, a)", ".b"]);
    expect(declarations("@media (x) { .a, .b { c: d; } } .a { c: d; }")).toEqual(["@media (x) .a", "@media (x) .b", ".a"]);
  });
});
