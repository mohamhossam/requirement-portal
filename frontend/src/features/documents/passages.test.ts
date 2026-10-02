import { describe, expect, it } from "vitest";

import { groupPassages, hiddenSheetOf, hiddenSheetTitles, type EvidenceBlock } from "./passages";

const block = (id: string, kind: EvidenceBlock["kind"], section: string, text: string | null, label = id): EvidenceBlock =>
  ({ id, kind, ordinal: 0, section_path: [section], label, text, asset_id: null });

describe("groupPassages", () => {
  it("gathers a Word table's rows into one grid, in column order", () => {
    const runs = groupPassages([
      block("p", "paragraph", "Heading", "Intro"),
      block("r1", "table_row", "Table 1", "R1C1: Plan | R1C2: Speed | R1C10: Note"),
      block("r2", "table_row", "Table 1", "R2C1: Starter | R2C2: 100 Mbps"),
      block("q", "paragraph", "Heading", "After"),
    ]);
    expect(runs.map((run) => run.type)).toEqual(["passage", "grid", "passage"]);
    const grid = runs[1];
    if (grid?.type !== "grid") throw new Error("expected a grid");
    expect(grid.columns).toEqual(["1", "2", "10"]);
    expect(grid.rows.map((row) => [row.number, row.cells["1"], row.first])).toEqual([[1, "Plan", true], [2, "Starter", true]]);
  });

  it("splits runs at a change of table or sheet", () => {
    const runs = groupPassages([
      block("a", "worksheet_range", "Worksheet 1", "A1=Plan"),
      block("b", "worksheet_range", "Worksheet 2", "A1=Plan"),
    ]);
    expect(runs.map((run) => run.type)).toEqual(["grid", "grid"]);
  });

  it("leaves a run as written when any row cannot be read as cells", () => {
    const runs = groupPassages([
      block("a", "table_row", "Table 1", "R1C1: Plan | R1C2: Speed"),
      block("b", "table_row", "Table 1", "R2C1: Starter [merged] | continues"),
    ]);
    expect(runs.map((run) => run.type)).toEqual(["passage", "passage"]);
  });
});

describe("hidden sheets", () => {
  it("finds a passage's hidden sheet and the sheet's own title", () => {
    const heading = block("h", "heading", "Hidden worksheet: Worksheet 2", "Margin model", "Hidden worksheet: Worksheet 2");
    const row = block("r", "worksheet_range", "Hidden worksheet: Worksheet 2", "A1=Plan");
    const visible = block("v", "worksheet_range", "Worksheet 1", "A1=Plan");
    expect(hiddenSheetOf(row, ["Worksheet 2"])).toBe("Worksheet 2");
    expect(hiddenSheetOf(visible, ["Worksheet 2"])).toBeNull();
    expect(hiddenSheetTitles([heading, row], ["Worksheet 2"]).get("Worksheet 2")).toBe("Margin model");
  });
});
