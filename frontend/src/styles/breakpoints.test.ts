import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The app folds at three widths and may fold at no others.
 *
 * It reached seven — 640, 700, 760, 850, 899, 900, 1050 — one visual generation
 * at a time, with 899 and 900 a pixel apart in different files. A comment asking
 * for restraint did not hold the line for four slices, so this does.
 *
 * Adding a fourth tier is allowed; it is a decision, made here and in
 * docs/architecture/adr-0049-three-breakpoints.md, rather than a rule dropped
 * into whichever stylesheet was open at the time.
 */
const TIERS = ["--breakpoint-sm", "--breakpoint-md", "--breakpoint-lg"];
// Relative to the package root, which is where vitest runs.
const DIRECTORY = join(process.cwd(), "src", "styles");

function stylesheets() {
  return readdirSync(DIRECTORY)
    .filter((name) => name.endsWith(".css"))
    .map((name) => [name, readFileSync(join(DIRECTORY, name), "utf8")] as const);
}

describe("breakpoints", () => {
  it("names every width query after one of the three tiers", () => {
    const offenders: string[] = [];
    for (const [name, css] of stylesheets()) {
      for (const [query] of css.matchAll(/@media[^{]+/g)) {
        const condition = query.replace("@media", "").trim();
        // Queries about capability rather than width are not tiers.
        if (/prefers-|hover|pointer|orientation|print/.test(condition)) continue;
        const tier = condition.match(/theme\((--breakpoint-[a-z]+)\)/)?.[1];
        if (!tier || !TIERS.includes(tier)) offenders.push(`${name}: ${condition}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("declares all three tiers in one unit", () => {
    // Tailwind sorts variant media queries by value only within a unit. Its
    // default `sm` is 40rem, which it emitted after the px `lg`, so `sm:`
    // overrode `lg:` on the same property at every desktop width.
    const entry = readFileSync(join(DIRECTORY, "index.css"), "utf8");
    expect(entry).toMatch(/--breakpoint-sm:\s*640px/);
    expect(entry).toMatch(/--breakpoint-md:\s*900px/);
    expect(entry).toMatch(/--breakpoint-lg:\s*1050px/);
  });

  it("keeps raw pixel widths out of media queries", () => {
    const offenders: string[] = [];
    for (const [name, css] of stylesheets()) {
      for (const [query] of css.matchAll(/@media[^{]+/g)) {
        if (/\d+(px|rem)/.test(query)) offenders.push(`${name}: ${query.trim()}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
