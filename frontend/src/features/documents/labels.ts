import type { components } from "../../api/schema";
import type { DocumentSummary } from "../../api/client";
import type { BadgeTone } from "../../components/ui";

/**
 * The attachment list's vocabulary, in the words of the person who attached the
 * file.
 *
 * The list printed `analysis_readiness` and the ingestion stage through
 * `.replaceAll("_", " ")` and CSS `capitalize` — "V1 · Ready", "Failed",
 * "Ready for review" — and called the files "prompt attachments". A business
 * owner never has to know there is a prompt.
 */
type Readiness = DocumentSummary["current_version"]["analysis_readiness"];
type Stage = components["schemas"]["IngestionStage"];

export const READINESS: Record<Readiness, { label: string; tone: BadgeTone }> = {
  ready: { label: "Ready", tone: "success" },
  ready_with_warnings: { label: "Ready, with warnings", tone: "warning" },
  blocked: { label: "Could not be read", tone: "danger" },
};

export const STAGE: Record<Stage, { label: string; tone: BadgeTone }> = {
  queued: { label: "Waiting to be processed", tone: "neutral" },
  scanning: { label: "Checking the file is safe", tone: "neutral" },
  extracting: { label: "Reading the file", tone: "neutral" },
  ready_for_review: { label: "Adding it to the requirement", tone: "neutral" },
  failed: { label: "Could not be read", tone: "danger" },
  quarantined: { label: "Blocked as unsafe", tone: "danger" },
  cancelled: { label: "Processing cancelled", tone: "neutral" },
};

export const ACCEPTED_FORMATS =
  "PDF, Word, PowerPoint, Excel, CSV, TSV, plain text, Markdown, PNG or JPG, up to 10 MB each";

export function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 1024 * 100 ? 1 : 0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/**
 * What the reader found in the file, only where it found something. "0 sections
 * · 0 tables · 0 images" on a text file read as a fault, and was printed red.
 */
export function evidenceLabel(summary: DocumentSummary["current_version"]["evidence_summary"]): string | null {
  const parts = [
    summary.section_count > 0 && plural(summary.section_count, "section", "sections"),
    summary.table_count > 0 && plural(summary.table_count, "table", "tables"),
    summary.image_count > 0 && plural(summary.image_count, "image", "images"),
    summary.worksheet_count > 0 && plural(summary.worksheet_count, "worksheet", "worksheets"),
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}

/**
 * A file's type as a person names it. The catalogue printed the MIME type —
 * `application/vnd.openxmlformats-officedocument.wordprocessingml.document` —
 * which wrapped onto three lines and told nobody anything the extension did not.
 */
const FILE_TYPES: Record<string, string> = {
  "application/pdf": "PDF",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel workbook",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint deck",
  "text/csv": "CSV table",
  "text/tab-separated-values": "TSV table",
  "text/plain": "Plain text",
  "text/markdown": "Markdown",
  "image/png": "PNG image",
  "image/jpeg": "JPG image",
};

export function fileTypeLabel(mimeType: string): string {
  return FILE_TYPES[mimeType] ?? "File";
}

type BlockKind = components["schemas"]["EvidenceBlockKind"];

/** What kind of passage the reader took from the file. */
export const BLOCK_KIND: Record<BlockKind, string> = {
  heading: "Heading",
  paragraph: "Paragraph",
  list_item: "List item",
  table_row: "Table row",
  image: "Image",
  worksheet_range: "Worksheet cells",
  external_reference: "Link, not opened",
};

type Severity = components["schemas"]["ExtractionWarningSeverity"];

/**
 * An extraction warning's weight, in words and in the reserved colours. It was
 * printed as the raw severity in tracked uppercase — "WARNING", "BLOCKING".
 */
export const SEVERITY: Record<Severity, { label: string; tone: BadgeTone }> = {
  blocking: { label: "Blocks analysis", tone: "danger" },
  warning: { label: "Check this", tone: "warning" },
  info: { label: "Note", tone: "neutral" },
};

type Version = DocumentSummary["current_version"];
type Warning = Version["extraction_warnings"][number];

/**
 * Warnings that describe how a file *type* is read, not anything about this
 * file. Every Word, Markdown, Excel, CSV and PowerPoint file carries one — "Word
 * headings, paragraphs and list items use neutral paragraph locations…" — so
 * shown as warnings they turned six of eight files amber and taught people to
 * ignore amber. They are kept, and shown, as reading notes.
 *
 * An explicit list rather than a rule like "no passage attached": a referenced
 * file that was not opened has no passage either, and it is exactly the kind of
 * thing a person has to act on.
 */
const READING_NOTES = new Set([
  "word_prose_structure",
  "word_table_structure",
  "worksheet_name_structure",
  "text_section_structure",
  "delimited_row_structure",
  "slide_table_structure",
]);

export function isReadingNote(warning: Warning): boolean {
  return warning.severity !== "blocking" && READING_NOTES.has(warning.code);
}

/**
 * Readiness as a person should weigh it. "Ready, with warnings" whose only
 * warnings are reading notes is ready: the file was read, and nothing about it
 * needs a decision.
 */
export function readinessView(version: Version): { label: string; tone: BadgeTone; notes: boolean } {
  const notes = version.extraction_warnings.some(isReadingNote);
  if (version.analysis_readiness === "ready_with_warnings" && version.extraction_warnings.every(isReadingNote)) {
    return { ...READINESS.ready, notes };
  }
  return { ...READINESS[version.analysis_readiness], notes };
}

/** A date and time a person reads at a glance: "26 Sep 2026, 15:20". */
export function dateTimeLabel(raw: string): string {
  return new Date(raw).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** Why analysis cannot start yet, for `analysis_eligibility.missing_fields`. */
const MISSING: Record<string, string> = {
  title: "a title",
  description: "the business need, or a file included in analysis",
  attachment_review: "a decision on a file that could not be read",
};

export function missingLabel(fields: string[]): string {
  const words = fields.map((field) => MISSING[field] ?? field.replaceAll("_", " "));
  if (words.length <= 1) return words.join("");
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}
