import type { components } from "../api/schema";

import { Disclosure } from "./Disclosure";

type Provenance = components["schemas"]["ProvenanceResponse"];

/**
 * The same format StalenessNotice uses. `toLocaleString()` with no options
 * picks its own, so the two timestamps a person sees side by side on the
 * workspace were written differently.
 */
const TIMESTAMP = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

export function ProvenanceDetails({
  provenance,
  label = "Original AI generation",
}: {
  provenance: Provenance;
  /**
   * What this record is of. Two of these can sit within a screen of each other
   * — the Story's own generation and its quality review's — and two disclosures
   * with the same accessible name are two controls a screen reader cannot tell
   * apart.
   */
  label?: string;
}) {
  return (
    <Disclosure className="text-meta text-ink-muted" label={label}>
      <dl className="m-0 flex flex-wrap gap-x-6 gap-y-3">
        <div className="grid gap-0.5">
          <dt className="text-label text-ink-muted">Model</dt>
          <dd className="text-ink-soft m-0 font-mono">{provenance.model}</dd>
        </div>
        <div className="grid gap-0.5">
          <dt className="text-label text-ink-muted">Prompt</dt>
          <dd className="text-ink-soft m-0 font-mono">{provenance.prompt_version}</dd>
        </div>
        <div className="grid gap-0.5">
          <dt className="text-label text-ink-muted">Generated</dt>
          {/* Not the machine register: §5 keeps mono for IDs, checksums and
              fingerprints, and "20 Sep 2026, 14:32" is none of those. */}
          <dd className="text-ink-soft m-0 font-sans">{TIMESTAMP.format(new Date(provenance.generated_at))}</dd>
        </div>
      </dl>
    </Disclosure>
  );
}
