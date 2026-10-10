import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, ExternalLink, FileUp } from "lucide-react";
import { useEffect, useId, useMemo, useRef } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import { ApiError, errorMessage, errorReference } from "../api/errors";
import { Disclosure } from "../components/Disclosure";
import { PageHeader } from "../components/shell";
import { ErrorNotice, ErrorState, LoadingState, Skeleton } from "../components/states";
import { Badge, Button, ButtonLink, Card, CardHeader, Checkbox, cx } from "../components/ui";
import { buttonClass } from "../components/ui/buttonClass";
import { EvidencePassages } from "../features/documents/EvidencePassages";
import {
  ACCEPTED_FORMATS,
  dateTimeLabel,
  evidenceLabel,
  fileTypeLabel,
  isReadingNote,
  readinessView,
  SEVERITY,
  sizeLabel,
} from "../features/documents/labels";
import { hiddenSheetTitles } from "../features/documents/passages";
import { useDocumentOwners } from "../features/documents/useDocumentOwners";
import { queryKeys } from "./queryKeys";
import { useDocumentTitle } from "./useDocumentTitle";

/** The same formats a file can be attached in; a new version goes through the same upload. */
const ACCEPT = ".pdf,.docx,.pptx,.xlsx,.csv,.tsv,.txt,.md,.png,.jpg,.jpeg";
const MEASURE = "max-w-[var(--measure-interface)]";

/**
 * One source file: is it trustworthy, and should analysis read it?
 * (docs/ux-plan.md §1 and Phase 7.)
 *
 * One card answers the question in the order a person decides — whether the
 * file could be read, what to check, which hidden sheets go, then the decision
 * with its consequence underneath. The passages follow, marked where they will
 * not be sent; the record of the file sits beside the card at `lg` and after
 * the passages below it, because on a narrow screen a checksum is not what a
 * person scrolled down for.
 *
 * An unreadable file is a different page: its card says so once, in plain
 * words, with the fix inside it, and there are no passages to show.
 */
export function DocumentDetailPage() {
  const { documentId = "" } = useParams();
  const versionInputId = useId();
  const versionInput = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const document = useQuery({
    queryKey: queryKeys.document(documentId),
    queryFn: ({ signal }) => api.getDocument(documentId, { signal }),
    enabled: Boolean(documentId),
  });
  const pdf = useQuery({
    queryKey: queryKeys.scope("document-pdf", documentId),
    queryFn: ({ signal }) => api.getDocumentPdf(documentId, { signal }),
    enabled: document.data?.current_version.mime_type === "application/pdf",
  });
  const pdfUrl = useMemo(() => pdf.data ? URL.createObjectURL(pdf.data) : null, [pdf.data]);
  useEffect(() => () => { if (pdfUrl) URL.revokeObjectURL(pdfUrl); }, [pdfUrl]);
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.document(documentId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.documents() }),
    ]);
  };
  const inclusion = useMutation({
    mutationFn: (included: boolean) => api.setDocumentInclusion(
      document.data!.requirement_id!, documentId, included, document.data!.version,
    ),
    onSuccess: refresh,
  });
  const worksheets = useMutation({
    mutationFn: (names: string[]) => api.setHiddenWorksheetInclusion(
      document.data!.requirement_id!, documentId, names, document.data!.version,
    ),
    onSuccess: refresh,
  });
  const uploadVersion = useMutation({
    mutationFn: (file: File) => document.data?.requirement_id
      ? api.uploadRequirementDocumentVersion(
          document.data.requirement_id, documentId, file, document.data.version
        )
      : api.uploadDraftDocumentVersion(
          document.data!.draft_id!, documentId, file, document.data!.version
        ),
    onSuccess: refresh,
  });
  const ownerOf = useDocumentOwners(document.data ? [document.data] : undefined);
  // Above the error return, because a hook cannot be called after one.
  useDocumentTitle(
    document.data ? `${document.data.current_version.filename} · Documents` : "Document",
  );
  if (document.isError) {
    // A missing file is not a failure to retry: say so, without the id.
    const missing = document.error instanceof ApiError && document.error.status === 404;
    return (
      <ErrorState
        headingLevel="h2"
        title={missing ? "This document isn’t here" : "We couldn’t open this document"}
        message={missing ? "It may have been removed, or the link may be wrong." : errorMessage(document.error)}
        reference={errorReference(document.error)}
        onRetry={missing ? undefined : () => void document.refetch()}
        action={<ButtonLink variant="secondary" to="/documents">Back to documents</ButtonLink>}
      />
    );
  }
  const data = document.data;
  const current = data?.current_version;
  const currentDetail = data?.versions.at(-1);
  const back = (
    <Link className="text-ink-muted text-meta mb-3 inline-flex min-h-6 items-center gap-1 no-underline hover:underline" to="/documents">
      <ArrowLeft size={16} aria-hidden="true" /> Documents
    </Link>
  );
  if (!data || !current || !currentDetail) {
    return <div>{back}<LoadingState label="Loading document" variant="page" /></div>;
  }

  const owner = ownerOf(data);
  const readiness = readinessView(current);
  const blocked = current.analysis_readiness === "blocked";
  const unread = current.extraction_status === "failed";
  const evidence = evidenceLabel(current.evidence_summary);
  const toCheck = current.extraction_warnings.filter((warning) => !isReadingNote(warning));
  const notes = current.extraction_warnings.filter(isReadingNote);
  const flagged = new Set(toCheck.flatMap((warning) => warning.block_id ? [warning.block_id] : []));
  const sheetTitles = hiddenSheetTitles(currentDetail.evidence_blocks, data.hidden_worksheets);
  const decisionError = inclusion.error ?? worksheets.error;
  const cardTone = blocked ? "danger" : data.requires_attention ? "warning" : "default";
  const pickFile = () => versionInput.current?.click();
  const usedVersion = data.versions.find((version) => version.id === data.included_version_id);

  const uploadButton = (variant: "primary" | "secondary", label: string) => (
    <Button
      variant={variant}
      icon={<FileUp size={16} aria-hidden="true" />}
      loading={uploadVersion.isPending}
      loadingLabel="Uploading…"
      onClick={pickFile}
    >
      {label}
    </Button>
  );
  const draftLink = owner?.kind === "draft" && (
    <Link className="text-accent underline underline-offset-2" to={owner.to}>Open the draft</Link>
  );

  const isPdf = current.mime_type === "application/pdf";
  const sent = data.included_in_analysis;
  // A left-out file's passages are shown — a person decides on them — but not
  // under "What analysis reads", which for them is not true.
  const passages = !unread && (
    <div className={cx("grid min-w-0 items-start gap-6", isPdf && "lg:grid-cols-2")}>
      {isPdf && (
        <section className="grid min-w-0 gap-4" aria-labelledby="original-title">
          <header className="flex flex-wrap items-end justify-between gap-3">
            <div className="grid gap-1">
              <h2 className="text-headline text-ink m-0" id="original-title">Original</h2>
              <p className={cx("text-meta text-ink-muted m-0", MEASURE)}>The PDF as uploaded, shown safely. Scripts and links inside it do not run.</p>
            </div>
            {pdfUrl && (
              <a className={buttonClass("secondary")} href={pdfUrl} target="_blank" rel="noreferrer">
                <ExternalLink size={16} aria-hidden="true" /> Open in a new tab
              </a>
            )}
          </header>
          {pdf.isError
            ? <ErrorNotice message={errorMessage(pdf.error)} reference={errorReference(pdf.error)} />
            : pdfUrl
              ? <iframe className="border-line bg-surface block min-h-[42rem] w-full rounded-md border border-solid" title={`Preview of ${current.filename}`} src={pdfUrl} />
              : <Skeleton label="Loading protected PDF" />}
        </section>
      )}
      <section className="grid min-w-0 gap-4" aria-labelledby="passages-title">
        <header className="grid gap-1">
          <h2 className="text-headline text-ink m-0" id="passages-title">
            {sent ? "What analysis reads" : "What analysis would read"}
          </h2>
          <p className={cx("text-meta text-ink-muted m-0", MEASURE)}>
            {sent
              ? `The passages taken from the file, as they are sent. Check them against the ${isPdf ? "original beside them" : "original"}.`
              : "This file is left out of analysis, so nothing below is sent. These are the passages analysis would read if it were included."}
          </p>
        </header>
        <EvidencePassages
          documentId={documentId}
          versionId={current.id}
          blocks={currentDetail.evidence_blocks}
          flagged={flagged}
          hiddenSheets={data.hidden_worksheets}
          includedHiddenSheets={data.included_hidden_worksheets}
          sent={sent}
          // Beside the original there is no room for an outline, and a PDF's
          // page images repeat the original: they are one click away instead.
          beside={isPdf}
        />
      </section>
    </div>
  );

  return (
    <div>
      {back}
      <PageHeader
        title={current.filename}
        description={
          <>
            {fileTypeLabel(current.mime_type)} · {sizeLabel(current.size_bytes)} · Version {current.number}
            {data.version_count > 1 && ` of ${data.version_count}`}
            {owner && (
              <>
                {" "}· Attached to{" "}
                <Link className="text-accent hover:underline" to={owner.to}>
                  {owner.title ?? (owner.kind === "draft" ? "a draft" : "its requirement")}
                </Link>
                {owner.kind === "draft" && owner.title && " (draft)"}
              </>
            )}
          </>
        }
        // On an unreadable file the upload is the fix, so it lives in the card
        // as the page's one primary action rather than up here as well.
        actions={blocked ? undefined : uploadButton("secondary", "Upload new version")}
      />
      {/* Out of the tab order: the buttons are the control. A visually hidden
          input in the tab order was a stop whose focus ring nobody could see. */}
      <input
        ref={versionInput}
        id={versionInputId}
        aria-label="Upload new version"
        className="sr-only"
        tabIndex={-1}
        type="file"
        accept={ACCEPT}
        disabled={uploadVersion.isPending}
        onChange={(event) => { const file = event.target.files?.[0]; if (file) uploadVersion.mutate(file); }}
      />
      {uploadVersion.error && <div className="mb-6"><ErrorNotice message={errorMessage(uploadVersion.error)} reference={errorReference(uploadVersion.error)} /></div>}

      {/* DOM order is card, passages, record: the order a narrow screen reads
          them in. At `lg` the record is placed beside the card; it holds no
          controls, so the reading order never fights the tab order. */}
      <div className="grid items-start gap-x-6 gap-y-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Card tone={cardTone} padding="fluid" aria-labelledby="use-in-analysis" className="lg:col-start-1 lg:row-start-1">
          <CardHeader headingLevel="h2" title={<span id="use-in-analysis">Use in analysis</span>} />
          <div className="grid gap-5">
            {blocked ? (
              <div className="grid gap-3">
                <p className={cx("text-body text-ink m-0", MEASURE)}>
                  <strong className="font-semibold">Nothing in this file could be read.</strong>{" "}
                  It is often a scan or photo with no text in it, or a file that is damaged or password-protected.
                </p>
                {/* `requires_attention`: somebody asked for this file, and the
                    requirement cannot be analysed until they replace it or
                    leave it out. Said as the decision it is, with both ways out
                    beside each other — not as "left out", which it is not yet. */}
                {data.requires_attention ? (
                  <p className={cx("text-body text-ink m-0 font-semibold", MEASURE)}>
                    It blocks analysis of {owner?.kind === "draft" ? "the draft" : "this requirement"} until you
                    upload a readable version or leave it out.
                  </p>
                ) : (
                  <p className={cx("text-body text-ink-soft m-0", MEASURE)}>It is left out of analysis.</p>
                )}
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                  {uploadButton("primary", "Upload a readable version")}
                  {data.requirement_id && data.requires_attention && (
                    <Button variant="text" disabled={inclusion.isPending} onClick={() => inclusion.mutate(false)}>
                      Leave out of analysis
                    </Button>
                  )}
                  {!data.requirement_id && owner?.kind === "draft" && data.requires_attention && (
                    <Link className={buttonClass("text")} to={owner.to}>Leave it out on the draft</Link>
                  )}
                </div>
                <p className={cx("text-meta text-ink-muted m-0", MEASURE)}>{ACCEPTED_FORMATS}.</p>
                {current.extraction_error && (
                  <Disclosure label="What the reader reported">
                    <p className="text-meta text-ink-soft m-0">{current.extraction_error}</p>
                  </Disclosure>
                )}
              </div>
            ) : (
              <p className="text-body text-ink-soft m-0 flex flex-wrap items-center gap-x-2 gap-y-1">
                <Badge tone={readiness.tone}>{readiness.label}</Badge>
                {evidence && <span className="tabular-nums">Read {evidence}.</span>}
              </p>
            )}

            {!blocked && data.requires_attention && (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <p className={cx("text-body text-ink m-0", MEASURE)}>
                  This file blocks analysis until you upload a readable version or leave it out.
                </p>
                {data.requirement_id && (
                  <Button variant="text" disabled={inclusion.isPending} onClick={() => inclusion.mutate(false)}>
                    Leave out of analysis
                  </Button>
                )}
              </div>
            )}

            {toCheck.length > 0 && (
              <section className="grid gap-2" aria-labelledby="what-to-check">
                <h3 className="text-title text-ink m-0" id="what-to-check">
                  What to check <span className="text-ink-muted font-normal tabular-nums">({toCheck.length})</span>
                </h3>
                <ul className="m-0 grid list-none gap-3 p-0">
                  {toCheck.map((warning) => {
                    const severity = SEVERITY[warning.severity];
                    return (
                      <li className="grid items-start justify-items-start gap-1.5 sm:grid-cols-[auto_minmax(0,1fr)] sm:gap-3" key={`${warning.code}-${warning.block_id ?? "document"}`}>
                        <Badge tone={severity.tone}>{severity.label}</Badge>
                        <p className={cx("text-body text-ink-soft m-0", MEASURE)}>
                          {warning.message}
                          {warning.block_id && (
                            <>
                              {" "}
                              <a className={buttonClass("text")} href={`#block-${warning.block_id}`}>
                                Show in the file
                              </a>
                            </>
                          )}
                        </p>
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}

            {data.hidden_worksheets.length > 0 && data.requirement_id ? (
              <fieldset className="m-0 grid gap-2 border-0 p-0">
                <legend className="text-title text-ink mb-1 p-0">Hidden worksheets</legend>
                <p className="text-meta text-ink-muted m-0">Hidden sheets are not sent unless you tick them here.</p>
                {data.hidden_worksheets.map((name) => (
                  <Checkbox
                    key={name}
                    label={sheetTitles.get(name) ?? name}
                    hint={sheetTitles.has(name) ? `${name} in the workbook` : undefined}
                    checked={data.included_hidden_worksheets.includes(name)}
                    loading={worksheets.isPending}
                    loadingLabel="Saving hidden sheet choice…"
                    onChange={(event) => {
                      const selected = event.target.checked
                        ? [...data.included_hidden_worksheets, name]
                        : data.included_hidden_worksheets.filter((item) => item !== name);
                      worksheets.mutate(selected);
                    }}
                  />
                ))}
              </fieldset>
            ) : null}

            {decisionError && <ErrorNotice message={errorMessage(decisionError)} reference={errorReference(decisionError)} />}

            {/* The decision comes after what it rests on, and says what it
                means right under it. */}
            {data.requirement_id && !blocked && (
              <div className="grid gap-2 pt-4 [border-top:1px_solid_var(--line)]">
                <Checkbox
                  label="Include in analysis"
                  hint={`When included, the passages below${data.hidden_worksheets.length ? " — except hidden sheets you have not ticked —" : ""} are sent to the configured AI provider. Links and embedded code are never opened or run.`}
                  checked={data.included_in_analysis}
                  loading={inclusion.isPending}
                  loadingLabel="Saving…"
                  onChange={(event) => inclusion.mutate(event.target.checked)}
                />
              </div>
            )}
            {!data.requirement_id && data.draft_id && !blocked && (
              <p className={cx("text-body text-ink-soft m-0 flex flex-wrap items-center gap-x-2 gap-y-1 pt-4 [border-top:1px_solid_var(--line)]", MEASURE)}>
                {data.included_in_analysis ? (
                  <span className="text-ink inline-flex items-center gap-1 font-semibold">
                    <Check className="text-success shrink-0" size={16} aria-hidden="true" /> In analysis on the draft.
                  </span>
                ) : (
                  <span className="text-ink font-semibold">Left out on the draft.</span>
                )}
                <span>This file is on a draft, so that choice is made there.</span>
                {draftLink}
              </p>
            )}

            {notes.length > 0 && (
              <Disclosure label={`How this file type is read (${notes.length})`}>
                <ul className="m-0 grid gap-2 pl-5">
                  {notes.map((note) => (
                    <li className={cx("text-meta text-ink-soft", MEASURE)} key={note.code}>{note.message}</li>
                  ))}
                </ul>
              </Disclosure>
            )}
          </div>
        </Card>

        {passages && <div className="min-w-0 lg:col-span-2 lg:row-start-2">{passages}</div>}

        <Card inset padding="compact" aria-labelledby="file-record" className="lg:col-start-2 lg:row-start-1">
          <CardHeader headingLevel="h2" title={<span id="file-record">File record</span>} className="mb-2" />
          <p className="text-meta text-ink-soft m-0 mb-3">
            Stored exactly as uploaded. A version is never changed; a new upload becomes a new version.
          </p>
          <dl className="m-0 grid gap-3">
            {[
              ["Type", fileTypeLabel(current.mime_type)],
              ["Size", sizeLabel(current.size_bytes)],
              ["Added", dateTimeLabel(current.created_at)],
              ...(unread ? [] : [["Passages", current.evidence_summary.block_count.toLocaleString()]]),
              // Which version analysis actually reads. A new upload is not
              // included until someone includes it, so on a file with several
              // versions this is not always the current one.
              ["Analysis reads", usedVersion ? `Version ${usedVersion.number}` : data.requires_attention ? "None yet, it blocks analysis" : "None, it is left out"],
            ].map(([term, value]) => (
              <div className="grid grid-cols-[6rem_minmax(0,1fr)] gap-2" key={term}>
                <dt className="text-label text-ink-muted pt-0.5">{term}</dt>
                <dd className="text-body text-ink m-0 tabular-nums">{value}</dd>
              </div>
            ))}
            <div className="grid gap-1">
              <dt className="text-label text-ink-muted">Checksum (SHA-256)</dt>
              <dd className="m-0 grid gap-1">
                <code className="text-mono text-ink-soft break-all">{current.checksum_sha256}</code>
                <span className="text-meta text-ink-muted">A fingerprint of the file. A copy with the same value is the same file, byte for byte.</span>
              </dd>
            </div>
          </dl>
          {data.versions.length > 1 && (
            <>
              <h3 className="text-label text-ink-muted mt-5 mb-2">Versions</h3>
              <ol className="m-0 grid list-none p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">
                {[...data.versions].reverse().map((version) => (
                  <li className="grid gap-0.5 py-2" key={version.id}>
                    <span className="text-body text-ink flex flex-wrap items-center gap-2 font-semibold">
                      <span>Version {version.number}</span>
                      {version.id === current.id && <Badge tone="neutral">Current</Badge>}
                      {version.id === data.included_version_id && <Badge tone="success">Used by analysis</Badge>}
                    </span>
                    <span className="text-meta text-ink-muted [overflow-wrap:anywhere]">
                      {version.filename} · {dateTimeLabel(version.created_at)}
                    </span>
                  </li>
                ))}
              </ol>
            </>
          )}
          {!blocked && (
            <p className="text-meta text-ink-muted m-0 mt-4">
              Upload new version accepts {ACCEPTED_FORMATS}. A new version is left out until you include it.
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}
