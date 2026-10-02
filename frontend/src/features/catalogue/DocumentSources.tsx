import { useMutation, useQuery } from "@tanstack/react-query";
import { FileSpreadsheet, FileText, Image as ImageIcon, Sparkles, Trash2, Upload } from "lucide-react";
import { useId, useRef, useState } from "react";

import { errorMessage } from "../../api/errors";
import {
  knowledgeApi,
  type ArchitectureJob,
  type KnowledgeDocument,
  type KnowledgeRelease,
} from "../../api/knowledge";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Button, Select, cx } from "../../components/ui";
import { JobStatus } from "./JobStatus";
import { catalogueKeys } from "./keys";
import { LANGUAGE_LABEL } from "./labels";

const ACCEPT = ".docx,.pdf,.xlsx,.csv,.tsv,.txt,.md,.markdown,.png,.jpg,.jpeg";
const FORMATS = "Word, PDF, Excel, CSV, TSV, plain text, Markdown or images (PNG, JPG)";
const IMAGE_NOTE = "Images feed suggestions only and are never quoted as evidence.";
const MIME: Record<string, string> = {
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  pdf: "application/pdf",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  csv: "text/csv",
  tsv: "text/tab-separated-values",
  txt: "text/plain",
  md: "text/markdown",
  markdown: "text/markdown",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
};

const SPREADSHEETS = new Set([MIME.xlsx, MIME.csv, MIME.tsv]);

/** Browsers disagree on the type of a .docx or .csv; the server checks name and type together. */
function typed(file: File): File {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  const type = MIME[extension];
  return type && file.type !== type ? new File([file], file.name, { type }) : file;
}

const READING_HINTS = {
  queued: "Waiting for the background worker. Other reading or index jobs may be ahead of it.",
  running: "Reading. Long documents on a local model can take several minutes.",
};

const title = (file: File) => file.name.replace(/\.[^.]+$/, "") || file.name;

/**
 * Where a draft's knowledge comes from. Each file added here is kept as an
 * immutable source and read by the AI straight away; what it finds waits below
 * as suggestions, and nothing reaches the catalogue until someone accepts it.
 */
export function DocumentSources({
  draft,
  onChanged,
}: {
  draft: KnowledgeRelease;
  onChanged: () => void;
}) {
  const inputId = useId();
  const fileInput = useRef<HTMLInputElement>(null);
  const [language, setLanguage] = useState("en");
  const [started, setStarted] = useState<Record<string, ArchitectureJob>>({});
  // The server's record of each document's reading job, so a reload or a second
  // tab shows the truth; polled while any of them is still waiting or running.
  const extractions = useQuery({
    queryKey: catalogueKeys.extractions(draft.id),
    queryFn: () => knowledgeApi.extractions(draft.id),
    refetchInterval: (query) =>
      (query.state.data ?? []).some((item) => ["queued", "running"].includes(item.job.status))
        ? 3000
        : false,
  });
  const jobs: Record<string, ArchitectureJob> = {
    ...started,
    ...Object.fromEntries((extractions.data ?? []).map((item) => [
      item.document_version_id,
      { ...item.job, error_category: item.job.error_category ?? null },
    ])),
  };
  const [status, setStatus] = useState("");
  const [removing, setRemoving] = useState<KnowledgeDocument | null>(null);

  const extract = useMutation({
    mutationFn: ({ release, versionId }: { release: KnowledgeRelease; versionId: string }) =>
      knowledgeApi.extract(release, versionId),
    onSuccess: (job, { versionId }) => {
      setStarted((current) => ({ ...current, [versionId]: job }));
      onChanged();
    },
  });
  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      let release = draft;
      for (const file of files) {
        release = await knowledgeApi.upload(release, typed(file), title(file), language);
        const added = release.documents[release.documents.length - 1];
        if (added) extract.mutate({ release, versionId: added.id });
      }
      return files.length;
    },
    onSuccess: (count) => {
      setStatus(`${count === 1 ? "1 document" : `${count} documents`} added. The AI is reading ${count === 1 ? "it" : "them"} now.`);
      onChanged();
    },
    onError: () => onChanged(),
  });
  const remove = useMutation({
    mutationFn: (document: KnowledgeDocument) => knowledgeApi.selectDocuments(
      draft, draft.documents.filter((item) => item.id !== document.id).map((item) => item.id),
    ),
    onSuccess: () => onChanged(),
  });
  const busy = upload.isPending || remove.isPending;
  const failure = upload.error ?? extract.error ?? remove.error;
  const start = (files: File[]) => {
    if (files.length && !busy) {
      setStatus("");
      upload.mutate(files);
    }
  };

  return (
    <section className="grid min-w-0 gap-4" aria-labelledby={`${inputId}-title`}>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid min-w-0 gap-1">
          <h3 className="text-title text-ink m-0" id={`${inputId}-title`}>From documents</h3>
          <p className="text-meta text-ink-muted m-0 max-w-[var(--measure-interface)]">
            The AI suggests catalogue content from each document, quoting its source. You decide what goes in.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <Select label="Document language" value={language} onChange={(event) => setLanguage(event.target.value)}
            fieldClassName="w-44">
            {Object.entries(LANGUAGE_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>
          <Button variant="primary" icon={<Upload size={16} aria-hidden="true" />} loading={upload.isPending}
            loadingLabel="Adding documents…" onClick={() => fileInput.current?.click()}>
            Add documents
          </Button>
        </div>
        <input ref={fileInput} id={inputId} className="sr-only" tabIndex={-1} type="file" multiple accept={ACCEPT}
          aria-label="Add documents" onChange={(event) => {
            start(Array.from(event.target.files ?? []));
            event.target.value = "";
          }} />
      </header>

      {/* Dragging is a shortcut, never the only way: Add documents does the same
          (WCAG 2.2 2.5.7). Below `sm` the zone gives way to the format line. */}
      <p className="text-meta text-ink-muted m-0 sm:hidden">{FORMATS}. {IMAGE_NOTE}</p>
      <div
        className="border-line-strong bg-surface-sunken hidden justify-items-center gap-1 rounded-md border border-dashed px-4 py-5 text-center sm:grid"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          start(Array.from(event.dataTransfer.files));
        }}
      >
        <p className={cx("text-body m-0", busy ? "text-ink-faint" : "text-ink")}>Drop documents here or use Add documents</p>
        <p className="text-meta text-ink-muted m-0">{FORMATS}. {IMAGE_NOTE}</p>
      </div>

      {failure && <ErrorNotice message={errorMessage(failure)} />}
      {status && <p className="text-meta text-ink-soft m-0" role="status">{status}</p>}

      {draft.documents.length === 0 ? (
        <p className="text-body text-ink-muted m-0">No source documents in this version yet.</p>
      ) : (
        <ul className="border-line m-0 grid list-none rounded-md border border-solid p-0 [&>li+li]:[border-top:1px_solid_var(--line)]"
          aria-label="Source documents in this version">
          {draft.documents.map((document) => {
            const image = document.mime_type.startsWith("image/");
            const Icon = image ? ImageIcon : SPREADSHEETS.has(document.mime_type) ? FileSpreadsheet : FileText;
            const job = jobs[document.id];
            return (
              <li key={document.id} className="grid gap-2 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-2">
                    <Icon className="text-ink-muted mt-0.5 shrink-0" size={16} aria-hidden="true" />
                    <div className="grid min-w-0">
                      <span className="text-body text-ink break-words">{document.title}</span>
                      <span className="text-meta text-ink-muted break-words">
                        {document.filename} · {LANGUAGE_LABEL[document.language] ?? document.language}
                        {image && " · suggestions only, not quoted in mapping"}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {!job && (
                      <Button size="sm" icon={<Sparkles size={14} aria-hidden="true" />}
                        loading={extract.isPending && extract.variables?.versionId === document.id}
                        loadingLabel="Starting…"
                        onClick={() => extract.mutate({ release: draft, versionId: document.id })}>
                        Suggest from this document
                      </Button>
                    )}
                    <Button size="sm" variant="ghost" icon={<Trash2 size={14} aria-hidden="true" />}
                      disabled={busy} onClick={() => setRemoving(document)}
                      aria-label={`Remove ${document.title} from this version`}>
                      Remove
                    </Button>
                  </div>
                </div>
                {job && (
                  <JobStatus key={`${job.id}-${job.attempts}`} job={job} label="Reading for suggestions"
                    hints={READING_HINTS} onFinished={onChanged} />
                )}
              </li>
            );
          })}
        </ul>
      )}
      {removing && (
        <ConfirmDialog
          title={`Remove “${removing.title}” from this version?`}
          message="It stops being a source for this version. To use it again, add the document again."
          confirmLabel="Remove document"
          onCancel={() => setRemoving(null)}
          onConfirm={() => { const document = removing; setRemoving(null); remove.mutate(document); }}
        />
      )}
    </section>
  );
}
