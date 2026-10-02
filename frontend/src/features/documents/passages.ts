import type { DocumentDetail } from "../../api/client";

export type EvidenceBlock = DocumentDetail["versions"][number]["evidence_blocks"][number];

const HIDDEN = "Hidden worksheet: ";

/**
 * The hidden worksheet a passage comes from, by the position name the API lists
 * in `hidden_worksheets` ("Worksheet 2"), or null.
 *
 * The reader files every passage of a hidden sheet under a section called
 * "Hidden worksheet: Worksheet 2". That wording is the only link between the
 * two, so a passage whose section does not match is treated as an ordinary one
 * rather than guessed at.
 */
export function hiddenSheetOf(block: EvidenceBlock, hiddenSheets: string[]): string | null {
  const section = block.section_path[0] ?? block.label;
  return hiddenSheets.find((name) => section === `${HIDDEN}${name}`) ?? null;
}

/**
 * Each hidden sheet's own name, from the heading passage that opens it — so a
 * checkbox can say "Margin model" where the API says "Worksheet 2".
 */
export function hiddenSheetTitles(blocks: EvidenceBlock[], hiddenSheets: string[]): Map<string, string> {
  const titles = new Map<string, string>();
  for (const block of blocks) {
    const sheet = block.kind === "heading" ? hiddenSheetOf(block, hiddenSheets) : null;
    const title = block.text?.trim();
    if (sheet && title && !titles.has(sheet)) titles.set(sheet, title);
  }
  return titles;
}

export type GridRow = { number: number; block: EvidenceBlock; first: boolean; cells: Record<string, string> };
export type PassageRun =
  | { type: "passage"; block: EvidenceBlock }
  | { type: "grid"; kind: "table_row" | "worksheet_range"; section: string; blocks: EvidenceBlock[]; columns: string[]; rows: GridRow[] };

type Cell = { row: number; column: string; text: string };
/* How the reader writes a table row ("R2C1: Starter | R2C2: 100 Mbps") and a
   worksheet range ("A2=Starter | B2=29"). */
const WORD_CELL = /^R(\d+)C(\d+):\s?([\s\S]*)$/;
const SHEET_CELL = /^([A-Z]{1,3})(\d+)=([\s\S]*)$/;

function parseCells(block: EvidenceBlock): Cell[] | null {
  if (!block.text) return null;
  const cells: Cell[] = [];
  for (const part of block.text.split(" | ")) {
    const word = block.kind === "table_row" ? WORD_CELL.exec(part) : null;
    const sheet = block.kind === "worksheet_range" ? SHEET_CELL.exec(part) : null;
    if (word) cells.push({ row: Number(word[1]), column: word[2] ?? "", text: word[3] ?? "" });
    else if (sheet) cells.push({ row: Number(sheet[2]), column: sheet[1] ?? "", text: sheet[3] ?? "" });
    // A cell whose own text contains " | ", or any marker this does not know,
    // leaves the part unmatched — and then the whole run stays as the reader
    // wrote it rather than being drawn as a table that could be wrong.
    else return null;
  }
  return cells.length ? cells : null;
}

function compareColumns(a: string, b: string) {
  const numeric = /^\d+$/;
  if (numeric.test(a) && numeric.test(b)) return Number(a) - Number(b);
  return a.length - b.length || a.localeCompare(b);
}

function toGrid(group: EvidenceBlock[]): { columns: string[]; rows: GridRow[] } | null {
  const rows: GridRow[] = [];
  const columns = new Set<string>();
  for (const block of group) {
    const cells = parseCells(block);
    if (!cells) return null;
    const byRow = new Map<number, Record<string, string>>();
    for (const cell of cells) {
      columns.add(cell.column);
      const row = byRow.get(cell.row) ?? {};
      row[cell.column] = cell.text;
      byRow.set(cell.row, row);
    }
    [...byRow.entries()]
      .sort(([a], [b]) => a - b)
      .forEach(([number, row], index) => rows.push({ number, block, first: index === 0, cells: row }));
  }
  return { columns: [...columns].sort(compareColumns), rows };
}

/**
 * The passages in reading order, with each unbroken run of rows from one table
 * or one worksheet gathered so it can be drawn as the table it was.
 *
 * "Check it against the original" was asked of a page that printed
 * `R1C1: Plan | R1C2: Speed | R1C3: Price` and `A1=Plan | B1=Monthly`. Nobody
 * compares that to a table by eye.
 */
export function groupPassages(blocks: EvidenceBlock[]): PassageRun[] {
  const runs: PassageRun[] = [];
  let group: EvidenceBlock[] = [];
  const flush = () => {
    const [first] = group;
    if (!first) return;
    const grid = toGrid(group);
    if (grid && (first.kind === "table_row" || first.kind === "worksheet_range")) {
      runs.push({ type: "grid", kind: first.kind, section: first.section_path[0] ?? first.label, blocks: group, ...grid });
    } else {
      group.forEach((item) => runs.push({ type: "passage", block: item }));
    }
    group = [];
  };
  const section = (block: EvidenceBlock) => block.section_path.join("\u0000");
  for (const block of blocks) {
    const tabular = block.kind === "table_row" || block.kind === "worksheet_range";
    const [first] = group;
    if (first && (!tabular || first.kind !== block.kind || section(first) !== section(block))) flush();
    if (tabular) group.push(block);
    else runs.push({ type: "passage", block });
  }
  flush();
  return runs;
}
