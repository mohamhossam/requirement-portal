import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Check, ExternalLink, FileText, Trash2, TriangleAlert, Upload } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api, type DocumentSummary } from "../../api/client";
import { errorMessage } from "../../api/errors";
import { ErrorNotice } from "../../components/ErrorNotice";
import { queryKeys } from "../../app/queryKeys";
import { Skeleton } from "../../components/Skeleton";
import { Badge, Button, Checkbox, cx, Modal, ModalFooter, ModalHeader } from "../../components/ui";
import { buttonClass } from "../../components/ui/buttonClass";
import { ACCEPTED_FORMATS, evidenceLabel, READINESS, sizeLabel, STAGE } from "./labels";

export type DocumentScope = { kind: "requirement" | "draft"; id: string };
export type AttachmentState = { hasIncludedAttachment: boolean; busy: boolean; blocked: boolean };
type UploadFailure = { id: number; file: File; message: string };
/* Actions drop to their own row under the filename below `sm`: at 390 a third
   column printed the Retry and Include controls over the file's status. */
const ROW = "grid grid-cols-[auto_minmax(0,1fr)] items-start gap-x-3 gap-y-2 py-3 sm:grid-cols-[auto_minmax(0,1fr)_auto]";
const ACTIONS = "col-start-2 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2 sm:col-start-3 sm:justify-end";
const FILENAME = "text-body text-ink font-semibold [overflow-wrap:anywhere]";

export function DocumentPanel({ scope, prepareScope, onContextChanged, readOnly = false,
  businessNeed = false, onStateChange, headingLevel = "h3" }: {
  scope: DocumentScope | null;
  prepareScope?: () => Promise<DocumentScope>;
  onContextChanged?: () => Promise<unknown> | void;
  readOnly?: boolean;
  businessNeed?: boolean;
  onStateChange?: (state: AttachmentState) => void;
  /** Where the panel sits in the page outline: its own section on Source, inside a form elsewhere. */
  headingLevel?: "h2" | "h3";
}) {
  const inputId = useId();
  const fileInput = useRef<HTMLInputElement>(null);
  const retryInput = useRef<HTMLInputElement>(null);
  const retryDocument = useRef<DocumentSummary | null>(null);
  const uploadingRef = useRef(false);
  const submissionKeys = useRef(new WeakMap<File, string>());
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [selection, setSelection] = useState<Record<string, boolean>>({});
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [failures, setFailures] = useState<UploadFailure[]>([]);
  const nextFailure = useRef(0);
  const [removing, setRemoving] = useState<DocumentSummary | null>(null);
  const cancelRemove = useRef<HTMLButtonElement>(null);
  const queryKey = scope?.kind === "requirement" ? queryKeys.requirementDocuments(scope.id)
    : queryKeys.draftDocuments(scope?.id ?? "pending");
  const documents = useQuery({
    queryKey,
    queryFn: () => scope?.kind === "requirement" ? api.listRequirementDocuments(scope.id)
      : api.listDraftDocuments(scope!.id),
    enabled: Boolean(scope),
  });
  const ingestions = useQuery({
    queryKey: ["attachment-ingestions", scope?.kind, scope?.id],
    queryFn: () => api.listAttachmentIngestions(scope!.id, scope!.kind === "draft"),
    enabled: Boolean(scope),
    refetchInterval: query => query.state.data?.some(item =>
      ["queued", "scanning", "extracting"].includes(item.stage)
      || item.stage === "ready_for_review" && !item.attached_document_id) ? 1000 : false,
  });
  const scopeKind = scope?.kind;
  const scopeId = scope?.id;
  const completed = ingestions.data?.filter(item => item.attached_document_id).map(item => item.id).join(",") ?? "";
  const completionCallback = useRef(onContextChanged);
  useEffect(() => { completionCallback.current = onContextChanged; }, [onContextChanged]);
  useEffect(() => {
    if (!completed) return;
    if (scopeId) void queryClient.invalidateQueries({ queryKey: scopeKind === "requirement" ? queryKeys.requirementDocuments(scopeId) : queryKeys.draftDocuments(scopeId) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.documents() });
    void completionCallback.current?.();
  }, [completed, queryClient, scopeKind, scopeId]);
  const processingControl = useMutation({
    mutationFn: ({ id, version, action }: { id: string; version: number; action: "retry" | "cancellation" | "exclusion" }) =>
      api.controlAttachment(scope!.id, scope!.kind === "draft", id, version, action),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attachment-ingestions", scope?.kind, scope?.id] }),
  });
  const processing = ingestions.data?.some(item => ["queued", "scanning", "extracting"].includes(item.stage)
    || item.stage === "ready_for_review" && !item.attached_document_id) ?? false;
  const refresh = async (resolved: DocumentScope) => {
    await queryClient.invalidateQueries({ queryKey: resolved.kind === "requirement"
      ? queryKeys.requirementDocuments(resolved.id) : queryKeys.draftDocuments(resolved.id) });
    await queryClient.invalidateQueries({ queryKey: ["attachment-ingestions", resolved.kind, resolved.id] });
    await queryClient.invalidateQueries({ queryKey: queryKeys.documents() });
    await onContextChanged?.();
  };
  const uploadFiles = async (files: File[], replacement?: DocumentSummary) => {
    if (uploadingRef.current || readOnly || !files.length) return;
    uploadingRef.current = true;
    setUploading(true);
    setPendingFiles(files);
    try {
      const resolved = scope ?? await prepareScope?.();
      if (!resolved) throw new Error("Save the draft before adding a document.");
      for (const file of files) {
        try {
          if (file.size > 10 * 1024 * 1024) throw new Error("File exceeds the 10 MB limit.");
          let key = submissionKeys.current.get(file);
          if (!key) { key = crypto.randomUUID(); submissionKeys.current.set(file, key); }
          const result = await api.submitAttachment(resolved.id, resolved.kind === "draft", file, key, businessNeed, replacement);
          setUploadStatus(`${result.filename} uploaded. Processing continues in the background.`);
          await refresh(resolved);
        } catch (failure) {
          setFailures((current) => [...current, { id: ++nextFailure.current, file, message: errorMessage(failure) }]);
        }
        setPendingFiles((current) => current.filter((pending) => pending !== file));
      }
      await refresh(resolved);
    } catch (failure) {
      setFailures((current) => [...current, ...files.map((file) => ({ id: ++nextFailure.current, file, message: errorMessage(failure) }))]);
    } finally {
      uploadingRef.current = false;
      setUploading(false);
      setPendingFiles([]);
      if (fileInput.current) fileInput.current.value = "";
      if (retryInput.current) retryInput.current.value = "";
    }
  };
  const inclusion = useMutation({
    mutationFn: ({ document, included }: { document: DocumentSummary; included: boolean }) =>
      scope!.kind === "draft"
        ? api.setDraftDocumentInclusion(scope!.id, document.id, included, document.version)
        : api.setDocumentInclusion(scope!.id, document.id, included, document.version),
    onSuccess: async () => { await refresh(scope!); },
    onSettled: () => setSelection({}),
  });
  const removal = useMutation({
    mutationFn: (document: DocumentSummary) => scope!.kind === "draft"
      ? api.removeDraftDocument(scope!.id, document.id, document.version)
      : api.removeDocument(scope!.id, document.id, document.version),
    onSuccess: async () => { await refresh(scope!); },
  });
  const mutating = uploading || inclusion.isPending || removal.isPending;
  const busy = mutating || Boolean(scope && (documents.isFetching || ingestions.isPending));
  const hasIncludedAttachment = Boolean(documents.data?.some((document) => document.included_in_analysis
    && document.current_version.analysis_readiness !== "blocked"));
  const blocked = processing || ingestions.isError || Boolean(ingestions.data?.some(item => !item.excluded && ["failed", "quarantined"].includes(item.stage))) || failures.length > 0 || inclusion.isError || removal.isError || Boolean(documents.isError || documents.data?.some((document) => document.requires_attention));
  const stateCallback = useRef(onStateChange);
  useEffect(() => { stateCallback.current = onStateChange; }, [onStateChange]);
  useEffect(() => { stateCallback.current?.({ hasIncludedAttachment, busy, blocked }); }, [hasIncludedAttachment, busy, blocked]);
  const failure = processingControl.error ?? ingestions.error ?? inclusion.error ?? removal.error ?? documents.error;
  const accept = ".pdf,.docx,.pptx,.xlsx,.csv,.tsv,.txt,.md,.png,.jpg,.jpeg";
  const Heading = headingLevel;

  return (
    <section className="grid min-w-0 gap-3" aria-labelledby={`${inputId}-title`}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid min-w-0 gap-1">
          <Heading className={cx(headingLevel === "h2" ? "text-headline" : "text-title", "text-ink m-0")} id={`${inputId}-title`}>
            {businessNeed ? "Attached files" : "Supporting evidence"}
          </Heading>
          <p className="text-meta text-ink-muted m-0 max-w-[var(--measure-interface)]">
            {businessNeed
              ? "Files ticked Include in analysis are read alongside the business need."
              : "Tick a file to include it in analysis."}
          </p>
        </div>
        <Button variant="secondary" disabled={readOnly || mutating} icon={<Upload size={16} aria-hidden="true" />}
          onClick={() => fileInput.current?.click()}>
          {uploading ? "Uploading…" : businessNeed ? "Attach files" : "Add file"}
        </Button>
        {/* Out of the tab order: the button above is the control, and a 1px
            input beside it was a second, invisible stop for the same act. */}
        <input ref={fileInput} id={inputId} className="sr-only" tabIndex={-1} type="file" multiple accept={accept}
          aria-label={businessNeed ? "Attach files" : "Add file"} disabled={readOnly || mutating}
          onChange={(event) => { void uploadFiles(Array.from(event.target.files ?? [])); }} />
        <input ref={retryInput} className="sr-only" tabIndex={-1} type="file" accept={accept} aria-label="Replacement file"
          disabled={readOnly || mutating} onChange={(event) => {
            const file = event.target.files?.[0];
            if (file && retryDocument.current) void uploadFiles([file], retryDocument.current);
          }} />
      </header>

      {/* Dragging is the shortcut, never the only way: Attach files does the
          same with one click (WCAG 2.2 2.5.7). Below `sm` nobody drags, so the
          zone gives way to the format line. */}
      {businessNeed && !readOnly && (
        <p className="text-meta text-ink-muted m-0 sm:hidden">{ACCEPTED_FORMATS}.</p>
      )}
      {businessNeed && !readOnly ? (
        <div
          className="border-line-strong bg-surface-sunken hidden justify-items-center sm:grid gap-1 rounded-md border border-dashed px-4 py-5 text-center"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault(); if (!busy) void uploadFiles(Array.from(event.dataTransfer.files));
          }}
        >
          <p className={cx("text-body m-0", busy ? "text-ink-faint" : "text-ink")}>Drop files here or use Attach files</p>
          <p className="text-meta text-ink-muted m-0 max-w-[64ch]">{ACCEPTED_FORMATS}. Export Figma designs as PNG, JPG or PDF.</p>
        </div>
      ) : (
        <p className="text-meta text-ink-muted m-0">{ACCEPTED_FORMATS}.</p>
      )}

      {failure && <ErrorNotice message={errorMessage(failure)} />}
      {!readOnly && (inclusion.isError || removal.isError || documents.isError) && <Button variant="text" className="w-fit" disabled={busy}
        onClick={async () => { inclusion.reset(); removal.reset(); if (scope) await refresh(scope); }}>Reload attachment state</Button>}
      {uploadStatus && (
        <p className="text-meta text-ink-soft m-0 flex items-center gap-1.5" role="status" aria-live="polite">
          <Check className="text-success shrink-0" size={14} aria-hidden="true" />{uploadStatus}
        </p>
      )}
      {uploading && <p className="sr-only" role="status">Uploading files…</p>}
      {!scope && <p className="text-meta text-ink-muted m-0">Choosing a file will start and save this draft.</p>}
      {scope && documents.isPending && <Skeleton label="Loading documents" bars={2} />}
      {documents.data?.length === 0 && !ingestions.data?.length && !pendingFiles.length && !failures.length && (
        <p className="text-meta text-ink-muted m-0">No files attached yet.</p>
      )}

      <ul className="m-0 grid list-none p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">
        {ingestions.data?.filter(item => !item.attached_document_id).map(item => {
          const stage = STAGE[item.stage];
          const failed = stage.tone === "danger";
          return <li className={ROW} key={`ingestion-${item.id}`}>
            {failed ? <AlertCircle className="text-danger mt-0.5" size={18} aria-hidden="true" />
              : <Upload className="text-ink-muted mt-0.5" size={18} aria-hidden="true" />}
            <div className="grid min-w-0 gap-1">
              <strong className={FILENAME}>{item.filename}</strong>
              <p className="m-0" role="status"><Badge tone={stage.tone}>{stage.label}</Badge></p>
              {item.error ? <p className="text-meta text-danger m-0">{item.error}</p> : null}
              {item.excluded ? <p className="text-meta text-ink-muted m-0">Left out of analysis. The failure stays on record.</p> : null}
            </div>
            <div className={ACTIONS}>
              {["queued", "scanning", "extracting"].includes(item.stage) ? <Button variant="text" disabled={readOnly || processingControl.isPending} onClick={() => processingControl.mutate({ ...item, action: "cancellation" })}>Cancel{" "}<span className="sr-only">processing {item.filename}</span></Button> : null}
              {["failed", "cancelled"].includes(item.stage) ? <Button variant="text" disabled={readOnly || processingControl.isPending} onClick={() => processingControl.mutate({ ...item, action: "retry" })}>Retry{" "}<span className="sr-only">processing {item.filename}</span></Button> : null}
              {!item.excluded && ["failed", "quarantined"].includes(item.stage) ? <Button variant="text" disabled={readOnly || processingControl.isPending} onClick={() => processingControl.mutate({ ...item, action: "exclusion" })}>Leave out{" "}<span className="sr-only">failed upload {item.filename}</span></Button> : null}
            </div>
          </li>;
        })}
        {pendingFiles.map((file, index) => <li className={ROW} key={`pending-${index}`}>
          <Upload className="text-ink-muted mt-0.5" size={18} aria-hidden="true" />
          <div className="grid min-w-0 gap-1"><strong className={FILENAME}>{file.name}</strong>
            <p className="text-meta text-ink-muted m-0">{sizeLabel(file.size)} · {index === 0 ? "Uploading…" : "Queued"}</p></div>
        </li>)}
        {documents.data?.map((document) => {
          const version = document.current_version;
          const readiness = READINESS[version.analysis_readiness];
          const evidence = evidenceLabel(version.evidence_summary);
          return <li className={ROW} key={document.id}>
            {version.analysis_readiness === "blocked"
              ? <AlertCircle className="text-danger mt-0.5" size={18} aria-hidden="true" />
              : <FileText className="text-ink-muted mt-0.5" size={18} aria-hidden="true" />}
            <div className="grid min-w-0 gap-1">
              <strong className={FILENAME}>{version.filename}</strong>
              <p className="text-meta text-ink-muted m-0 flex flex-wrap items-center gap-x-2 gap-y-1">
                <Badge tone={readiness.tone}>{readiness.label}</Badge>
                <span className="tabular-nums">{sizeLabel(version.size_bytes)} · Version {version.number}{evidence ? ` · ${evidence}` : ""}</span>
              </p>
              {version.extraction_error && <p className="text-meta text-danger m-0 flex items-start gap-1"><AlertCircle className="mt-0.5 shrink-0" size={13} aria-hidden="true" />{version.extraction_error}</p>}
              {version.extraction_warnings.map((warning) => <p className="text-meta text-warning m-0 flex items-start gap-1" key={`${warning.code}-${warning.block_id ?? "document"}`}><TriangleAlert className="mt-0.5 shrink-0" size={13} aria-hidden="true" />{warning.message}</p>)}
              {document.requires_attention && <p className="text-meta text-ink-soft m-0">Replace this file, or leave it out of analysis, before analysing.</p>}
            </div>
            <div className={ACTIONS}>
              <Checkbox
                checked={selection[document.id] ?? document.included_in_analysis}
                disabled={readOnly || busy || version.analysis_readiness === "blocked"}
                label={businessNeed ? "Include in analysis" : "Include"}
                onChange={(event) => {
                  const included = event.target.checked;
                  setSelection({ [document.id]: included });
                  inclusion.mutate({ document, included });
                }}
              />
              <Link className={buttonClass("ghost", "icon")} to={`/documents/${document.id}`} aria-label={`Review ${version.filename}`} title="Open the file">
                <ExternalLink size={16} aria-hidden="true" />
              </Link>
              {!readOnly && version.analysis_readiness === "blocked" && <Button variant="text" disabled={busy}
                onClick={() => { retryDocument.current = document; retryInput.current?.click(); }}>Replace file{" "}<span className="sr-only">{version.filename}</span></Button>}
              {!readOnly && document.requires_attention && <Button variant="text" disabled={busy}
                onClick={() => inclusion.mutate({ document, included: false })}>Leave out of analysis{" "}<span className="sr-only">{version.filename}</span></Button>}
              {!readOnly && <Button variant="ghost" size="icon" disabled={busy} onClick={() => setRemoving(document)}
                aria-label={`Remove ${version.filename}`} title="Remove file"><Trash2 size={16} aria-hidden="true" /></Button>}
            </div>
          </li>;
        })}
        {failures.map((item) => <li className={ROW} key={`failed-${item.id}`}>
          <AlertCircle className="text-danger mt-0.5" size={18} aria-hidden="true" />
          <div className="grid min-w-0 gap-1"><strong className={FILENAME}>{item.file.name}</strong>
            <p className="text-meta text-danger m-0">{item.message}</p></div>
          <div className={ACTIONS}><Button variant="text" disabled={busy} onClick={() => {
            setFailures((current) => current.filter((entry) => entry.id !== item.id)); void uploadFiles([item.file]);
          }}>Retry{" "}<span className="sr-only">{item.file.name}</span></Button><Button variant="text" disabled={busy}
            onClick={() => setFailures((current) => current.filter((entry) => entry.id !== item.id))}>Dismiss{" "}<span className="sr-only">{item.file.name}</span></Button></div>
        </li>)}
      </ul>

      {removing && (
        <Modal variant="dialog" labelledBy={`${inputId}-remove`} onClose={() => setRemoving(null)} initialFocus={cancelRemove}>
          <ModalHeader id={`${inputId}-remove`} title={`Remove ${removing.current_version.filename}?`}
            description="The file is taken off this requirement and out of its analysis." />
          <ModalFooter>
            <Button ref={cancelRemove} variant="text" onClick={() => setRemoving(null)}>Cancel</Button>
            <Button variant="danger" onClick={() => { const document = removing; setRemoving(null); removal.mutate(document); }}>
              Remove file
            </Button>
          </ModalFooter>
        </Modal>
      )}
    </section>
  );
}
