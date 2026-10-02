import { useMutation } from "@tanstack/react-query";
import { Download, FileSpreadsheet, Upload } from "lucide-react";
import { useId, useRef, useState } from "react";

import { errorMessage } from "../../api/errors";
import { knowledgeApi, type CatalogueDiff, type KnowledgeRelease } from "../../api/knowledge";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Button, Card } from "../../components/ui";
import { DiffList } from "./DiffList";

const ACCEPT = ".xlsx,.yaml,.yml,.json";

/**
 * Upload a whole catalogue as Excel (from the template), YAML or JSON. The file
 * is previewed against the draft first; nothing changes until "Replace".
 */
export function CatalogueFileImport({ draft, onChanged }: { draft: KnowledgeRelease; onChanged: () => void }) {
  const inputId = useId();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CatalogueDiff | null>(null);
  const [status, setStatus] = useState("");
  const check = useMutation({
    mutationFn: (chosen: File) => knowledgeApi.previewFile(draft, chosen),
    onSuccess: (diff) => setPreview(diff),
  });
  const apply = useMutation({
    mutationFn: (chosen: File) => knowledgeApi.importFile(draft, chosen),
    onSuccess: () => {
      setStatus(`${file?.name ?? "The file"} replaced this version’s systems and dependencies.`);
      setFile(null);
      setPreview(null);
      onChanged();
    },
  });
  const template = useMutation({ mutationFn: knowledgeApi.template });
  const failure = check.error ?? apply.error ?? template.error;

  return (
    <section className="grid min-w-0 gap-4" aria-labelledby={`${inputId}-title`}>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid gap-1">
          <h3 className="text-title text-ink m-0" id={`${inputId}-title`}>Upload a catalogue file</h3>
          <p className="text-meta text-ink-muted m-0 max-w-[var(--measure-interface)]">
            Fill in the Excel template, or upload YAML or JSON exported from another release. It replaces the
            draft’s systems, with their components and capabilities, and its dependencies; source documents stay.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button icon={<Download size={16} aria-hidden="true" />} loading={template.isPending}
            loadingLabel="Preparing…" onClick={() => template.mutate()}>
            Download Excel template
          </Button>
          <Button variant="primary" icon={<Upload size={16} aria-hidden="true" />} loading={check.isPending}
            loadingLabel="Checking the file…" onClick={() => input.current?.click()}>
            Choose a file
          </Button>
        </div>
        <input ref={input} id={inputId} className="sr-only" tabIndex={-1} type="file" accept={ACCEPT}
          aria-label="Choose a catalogue file" onChange={(event) => {
            const chosen = event.target.files?.[0];
            event.target.value = "";
            if (!chosen) return;
            setFile(chosen);
            setPreview(null);
            setStatus("");
            apply.reset();
            check.mutate(chosen);
          }} />
      </header>
      {failure && <ErrorNotice message={errorMessage(failure)} />}
      {status && <p className="text-meta text-ink-soft m-0" role="status">{status}</p>}
      {file && preview && (
        <Card padding="compact" inset className="grid gap-4" aria-labelledby={`${inputId}-preview`}>
          <div className="flex items-center gap-2">
            <FileSpreadsheet size={16} aria-hidden="true" className="text-ink-muted" />
            <h4 className="text-body text-ink m-0 font-semibold" id={`${inputId}-preview`}>
              What {file.name} would change in this version
            </h4>
          </div>
          <DiffList diff={preview} headingLevel="h5" empty="The file matches this version; importing it changes nothing." />
          <div className="flex flex-wrap justify-end gap-2">
            <Button onClick={() => { setFile(null); setPreview(null); }}>Keep this version as it is</Button>
            <Button variant="primary" loading={apply.isPending} loadingLabel="Replacing…"
              onClick={() => apply.mutate(file)}>
              Replace this version’s content with the file
            </Button>
          </div>
        </Card>
      )}
    </section>
  );
}
