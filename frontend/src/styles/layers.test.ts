import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Stacking comes from one named scale (docs/design-system.md §10.3):
 * --z-base 1, --z-sticky 10, --z-chrome 20, --z-overlay 40, --z-top 50.
 *
 * ux-plan.md §3.9 found nine distinct values across the stylesheets, including a
 * bare 100, and each one was somebody out-bidding the last. A number is not the
 * usual cause of "z-index isn't working" anyway — a positioned ancestor with its
 * own z-index opening a new stacking context is — so the fix for a layer that
 * sits wrong is to pick its tier, not a bigger number.
 *
 * `auto` and `0` are allowed: they opt out of layering rather than claim a tier.
 */
const SOURCE = join(process.cwd(), "src");
const TOKENS = join(SOURCE, "styles", "tokens.css");
const TIER = /^var\(--z-(base|sticky|chrome|overlay|top)\)$/;

function files(directory: string, extension: RegExp): string[] {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) return files(path, extension);
    return extension.test(name) ? [path] : [];
  });
}

const withoutComments = (text: string) => text.replace(/\/\*[\s\S]*?\*\//g, "");

describe("layers", () => {
  it("takes every stylesheet z-index from the scale", () => {
    const offenders: string[] = [];
    for (const path of files(SOURCE, /\.css$/)) {
      if (path === TOKENS) continue;
      for (const [, value] of withoutComments(readFileSync(path, "utf8")).matchAll(/z-index\s*:\s*([^;}]+)/g)) {
        const v = (value ?? "").replace(/!important/, "").trim();
        if (v !== "auto" && v !== "0" && !TIER.test(v)) offenders.push(`${relative(SOURCE, path)}: z-index: ${v}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("takes every z- utility in markup from the scale", () => {
    const offenders: string[] = [];
    for (const path of files(SOURCE, /\.tsx?$/)) {
      if (/\.test\.tsx?$/.test(path)) continue;
      for (const [utility, raw] of readFileSync(path, "utf8").matchAll(/(?<![\w-])-?z-(\[[^\]]+\]|\d+)(?![\w-])/g)) {
        const value = raw ?? "";
        const inner = value.startsWith("[") ? value.slice(1, -1) : "";
        if (value !== "0" && !TIER.test(inner)) offenders.push(`${relative(SOURCE, path)}: ${utility}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
