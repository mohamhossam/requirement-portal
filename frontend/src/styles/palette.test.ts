import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Colour comes from tokens.css and from nowhere else (docs/design-system.md §15).
 *
 * The stylesheets once carried 365 hardcoded colours across three abandoned
 * visual generations — a warm near-black, a vermilion, a teal — and every one of
 * them painted the same light value over the dark theme, because a literal does
 * not know which theme it is in. ux-plan.md §3.9 calls that drift "the single
 * largest tax" on the redesign. Phase 0 took the count to zero; this keeps it
 * there.
 *
 * A colour that is genuinely missing gets a token in tokens.css, with its dark
 * counterpart, and the component names the token.
 */
const SOURCE = join(process.cwd(), "src");
const TOKENS = join(SOURCE, "styles", "tokens.css");

/**
 * hex, rgb()/hsl() in CSS or in a Tailwind arbitrary value, and the two bare
 * keywords. A lookbehind rather than `\b` before `rgb(`: in an arbitrary value
 * such as `shadow-[0_2px_rgb(…)]` the underscore is a word character, so there
 * is no word boundary to find. `bg-white` / `text-black` are caught as keywords;
 * `white-space` is not.
 */
const LITERAL = /#[0-9a-fA-F]{3,8}\b|(?<![A-Za-z])(?:rgba?|hsla?)\(|(?<![\w])(?:white|black)(?![\w-])/;

function files(directory: string, extension: RegExp): string[] {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) return files(path, extension);
    return extension.test(name) ? [path] : [];
  });
}

/** Comments may name a retired colour — the notes recording what was removed do. */
function withoutComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
}

describe("palette", () => {
  it("keeps colour literals out of every stylesheet but tokens.css", () => {
    const offenders: string[] = [];
    for (const path of files(SOURCE, /\.css$/)) {
      if (path === TOKENS) continue;
      const css = withoutComments(readFileSync(path, "utf8"));
      for (const [declaration] of css.matchAll(/[^;{}]+:[^;{}]+/g)) {
        // A mask reads alpha only; its gradient stops are coverage, not colour.
        if (/^\s*(-webkit-)?mask(-image)?\s*:/.test(declaration)) continue;
        if (LITERAL.test(declaration)) {
          offenders.push(`${relative(SOURCE, path)}: ${declaration.trim()}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  it("keeps colour literals out of components", () => {
    const offenders: string[] = [];
    for (const path of files(SOURCE, /\.tsx?$/)) {
      // Tests assert on computed values; the generated API schema is not markup.
      if (/\.test\.tsx?$/.test(path) || path.endsWith("schema.d.ts")) continue;
      const lines = withoutComments(readFileSync(path, "utf8")).split("\n");
      lines.forEach((line, index) => {
        if (LITERAL.test(line)) offenders.push(`${relative(SOURCE, path)}:${index + 1}: ${line.trim()}`);
      });
    }
    expect(offenders).toEqual([]);
  });
});
