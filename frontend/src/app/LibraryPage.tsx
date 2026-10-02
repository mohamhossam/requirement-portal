import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, type LibraryDocument, type LibraryPassage, type ReferenceChunk } from "../api/client";
import { errorMessage } from "../api/errors";
import { PageHeader } from "../components/shell";
import { ErrorNotice, LoadingState } from "../components/states";
import { queryKeys } from "./queryKeys";
import { LibraryDependencies, LibraryOwnership } from "./LibraryGovernance";
import { useDocumentTitle } from "./useDocumentTitle";
import { OriginalPreview } from "../features/documents/OriginalPreview";
import "./library.css";
import { Button, ButtonLink } from "../components/ui/Button";

const STAGES: Record<LibraryDocument["versions"][number]["stage"], string> = {
  queued: "Queued for processing", scanning: "Checking file safety", extracting: "Extracting content",
  ready_for_review: "Ready for owner review", failed: "Processing failed", quarantined: "Quarantined", cancelled: "Processing cancelled",
};
function pending(document: LibraryDocument) {
  const latest = document.publications.at(-1);
  return document.versions.some(v => ["queued", "scanning", "extracting"].includes(v.stage)) ||
    !!latest && !latest.activated_at && !latest.withdrawn_at && !latest.built_at && latest.indexing_attempts < 3;
}

function RetrievalContext({ chunk }: { chunk: ReferenceChunk }) {
  if (!chunk.context_text || chunk.context_locations.length < 2) return null;
  return <details className="library-context">
    <summary>
      Surrounding approved context · {chunk.context_locations.length} passages · {chunk.context_token_count} budget units
    </summary>
    <p>The linked sentence remains the exact citation. This context helps interpret it and contains only owner-approved passages from the same section.</p>
    <p dir="auto" className="library-text">{chunk.context_text}</p>
  </details>;
}

function CorpusBuild({ document, dirty, refresh }: { document: LibraryDocument; dirty: boolean; refresh: () => void }) {
  const latest = document.publications.at(-1);
  const candidate = latest?.requires_activation && !latest.activated_at && !latest.withdrawn_at ? latest : undefined;
  const pendingApproval = latest && !latest.activated_at && !latest.withdrawn_at;
  const [acknowledged, setAcknowledged] = useState<string | null>(null);
  const preview = useMutation({ mutationFn: () => api.previewLibraryBuild(document.id) });
  const build = useMutation({ mutationFn: () => api.buildLibrary(document.id, preview.data!), onSuccess: refresh });
  const activate = useMutation({ mutationFn: () => api.activateLibraryBuild(document, candidate!.id, candidate!.chunk_manifest!), onSuccess: refresh });
  const discard = useMutation({ mutationFn: () => api.discardLibraryBuild(document, candidate!.id), onSuccess: refresh });
  const freshPreview = !dirty && preview.data?.document_version === document.version ? preview.data : undefined;
  const source = document.versions.at(-1)!;
  const currentSource = candidate?.version_id === source.id && candidate?.revision_id === source.revisions.at(-1)?.id;
  return <section aria-labelledby="corpus-build-heading">
    <h3 id="corpus-build-heading">Build table-aware search version</h3>
    <p>Keep table fields together and retain labels on long fields. Review the saved passages before building. Your current publication stays in search until you activate the new version.</p>
    {dirty ? <p role="status">Save your passage changes before previewing, building or activating.</p> : null}
    {!pendingApproval ? <>
      <Button variant="secondary" type="submit" disabled={dirty || preview.isPending} onClick={() => preview.mutate()}>{preview.isPending ? "Preparing preview…" : "Preview table-aware version"}</Button>
      {freshPreview ? <>
        <details open><summary>{freshPreview.chunks.length} table-aware chunks</summary>{freshPreview.chunks.map(c => <article key={c.id} className="library-passage">
          <h4 dir="auto">{c.location} · exact passage · {c.token_count} budget units</h4>
          {c.field_context ? <p dir="auto">Field label for context: {c.field_context}</p> : null}
          <p dir="auto" className="library-text">{c.original_text}</p>
          <RetrievalContext chunk={c} />
        </article>)}</details>
        <p>Approving this build shares only the saved selected passages when you later activate it. Applicability to Requirements still needs their owners' decisions.</p>
        <Button variant="primary" type="submit" disabled={build.isPending || source.blocking_warnings.length > 0 || freshPreview.chunks.length === 0} onClick={() => build.mutate()}>{build.isPending ? "Starting build…" : "Approve and build search version"}</Button>
      </> : null}
    </> : candidate ? <>
      <p role="status">{candidate.built_at ? `Build ready · ${candidate.chunk_count} chunks · awaiting your activation` : candidate.indexing_attempts >= 3 ? "Build stopped after three attempts. Use Retry indexing below, or discard this build." : "Building search version. You can leave this page and return later."}</p>
      {!currentSource ? <p>The saved source has changed. Discard this build, then preview and build the current review.</p> : null}
      {candidate.built_at ? <>
        <p>Activation replaces this document's current publication. Requirements citing the previous publication will need their owners to reconcile those references. Recorded decisions remain in history.</p>
        <label className="library-checkbox"><input type="checkbox" checked={acknowledged === candidate.id} onChange={e => setAcknowledged(e.target.checked ? candidate.id : null)} />I understand that previous citations will need reconciliation.</label>
        <Button variant="primary" type="submit" disabled={dirty || !currentSource || acknowledged !== candidate.id || activate.isPending || discard.isPending} onClick={() => activate.mutate()}>{activate.isPending ? "Activating…" : "Activate built version"}</Button>
      </> : null}
      <Button variant="secondary" type="submit" disabled={discard.isPending || activate.isPending} onClick={() => discard.mutate()}>Discard pending build</Button>
    </> : <p>Wait for the approved publication to finish indexing before starting another build.</p>}
    {preview.isError || build.isError || activate.isError || discard.isError ? <ErrorNotice message={errorMessage(preview.error ?? build.error ?? activate.error ?? discard.error)} /> : null}
    <details><summary>Search version history</summary><ul>{document.publications.map(p => <li key={p.id}>
      {p.id === document.published_id ? "Active" : p.withdrawn_at ? "Withdrawn or discarded" : p.built_at && !p.activated_at ? "Ready" : p.activated_at ? "Previous publication" : "Building"} · {p.chunking_policy} · {p.chunk_count ?? 0} chunks
      <p className="library-text">Build: {p.id}<br />Index: {p.index_identity ?? "Assigned during indexing"}<br />Manifest: {p.chunk_manifest ?? "Not completed"}</p>
    </li>)}</ul></details>
  </section>;
}

function Review({ document, refresh, onDirty }: { document: LibraryDocument; refresh: () => void; onDirty: () => void }) {
  const source = document.versions.at(-1)!;
  const [passages, setPassages] = useState<LibraryPassage[]>(() => source.revisions.at(-1)?.passages ??
    source.blocks.map(b => ({ block_id: b.id, text: b.text ?? `[Image: ${b.label}]`, included: !!b.text, exclusion_reason: "" })));
  const [explanation, setExplanation] = useState("");
  const [page, setPage] = useState(0);
  const save = useMutation({ mutationFn: () => api.reviewLibrary(document, source.id, passages, explanation), onSuccess: refresh });
  const update = (id: string, changes: Partial<LibraryPassage>) => { onDirty(); setPassages(items => items.map(p => p.block_id === id ? { ...p, ...changes } : p)); };
  return <section aria-labelledby="review-heading">
    <h2 id="review-heading">Review extracted passages</h2>
    <p>Compare with the original. Corrections create a new extraction revision; excluded passages require a reason.</p>
    {passages.slice(page * 20, page * 20 + 20).map(p => {
      const block = source.blocks.find(b => b.id === p.block_id)!;
      return <article className="library-passage" key={p.block_id} id={`block-${p.block_id}`}>
        <h3 dir="auto">{block.section_path.join(" / ")} · {block.label}</h3>
        <OriginalPreview documentId={document.id} versionId={source.id} blockId={block.id} />
        {source.warning_details?.filter(w => w.block_id === block.id).map(w => <p key={w.code} role="note">{w.message} {w.severity === "blocking" ? "Exclude this affected content with a reason to resolve this warning, or replace the source." : ""}</p>)}
        <div className="library-compare">
          <div><strong>Original extraction</strong><p dir="auto" className="library-text">{block.text ?? "No text was extracted from this image. Compare the source and enter a reviewed transcription, or exclude it with a reason."}</p></div>
          <label>Reviewed text<textarea dir="auto" rows={5} value={p.text} onChange={e => update(p.block_id, { text: e.target.value })} /></label>
        </div>
        <label className="library-checkbox"><input type="checkbox" checked={p.included} onChange={e => update(p.block_id, { included: e.target.checked })} />Include in shared publication</label>
        {!p.included ? <label>Reason for exclusion<input value={p.exclusion_reason ?? ""} onChange={e => update(p.block_id, { exclusion_reason: e.target.value })} /></label> : null}
      </article>;
    })}
    {passages.length > 20 ? <nav aria-label="Passage pages" className="library-actions">
      <Button variant="secondary" type="submit" disabled={page === 0} onClick={() => setPage(p => p - 1)}>Previous passages</Button>
      <span>Page {page + 1} of {Math.ceil(passages.length / 20)}</span>
      <Button variant="secondary" type="submit" disabled={(page + 1) * 20 >= passages.length} onClick={() => setPage(p => p + 1)}>Next passages</Button>
    </nav> : null}
    <label>Review summary<input value={explanation} onChange={e => setExplanation(e.target.value)} maxLength={2000} /></label>
    <Button variant="primary" type="submit" disabled={save.isPending || !explanation.trim() || !passages.length || passages.some(p => !p.text.trim() || (!p.included && !p.exclusion_reason?.trim()))} onClick={() => save.mutate()}>
      {save.isPending ? "Saving review…" : "Save extraction review"}
    </Button>
    {save.isError ? <ErrorNotice message={errorMessage(save.error)} /> : null}
    {save.isSuccess ? <p role="status">Review saved. Approve this exact revision when ready.</p> : null}
  </section>;
}

function Detail({ document, refresh }: { document: LibraryDocument; refresh: () => void }) {
  const source = document.versions.at(-1)!;
  const [reason, setReason] = useState("");
  const [dirtyRevision, setDirtyRevision] = useState<string | null>(null);
  const revisionKey = `${source.id}:${source.revisions.at(-1)?.id ?? "initial"}`;
  const dirty = dirtyRevision === revisionKey;
  const [replacement, setReplacement] = useState<File | null>(null);
  const [replacementKey, setReplacementKey] = useState(() => crypto.randomUUID());
  const replaceFile = useMutation({ mutationFn: () => api.uploadLibrary(replacement!, document.title, replacementKey, document), onSuccess: () => { setReplacement(null); setReplacementKey(crypto.randomUUID()); refresh(); } });
  const mutation = useMutation({ mutationFn: (action: "approve" | "withdraw" | "retry" | "cancellation") =>
    action === "approve" ? api.approveLibrary(document) : action === "withdraw" ? api.withdrawLibrary(document, reason) : api.controlLibrary(document, action), onSuccess: refresh });
  const download = useMutation({ mutationFn: () => api.downloadLibrary(document.id, source.id, source.filename) });
  const approval = document.publications.at(-1);
  const currentApproval = approval?.version_id === source.id ? approval : undefined;
  const published = document.publications.find(p => p.id === document.published_id);
  const publishedVersion = document.versions.find(v => v.id === published?.version_id);
  const preview = useMutation({ mutationFn: () => api.previewLibraryChunks(document.id) });
  const retryIndex = useMutation({ mutationFn: () => api.retryLibraryIndex(document), onSuccess: refresh });
  return <div className="library-detail">
    <h2 dir="auto">{document.title}</h2>
    <p>Owner: {document.owner.display_name} · File version {source.number} · {STAGES[source.stage]}</p>
    <p role="status">{currentApproval?.withdrawn_at ? (published ? "Previous publication remains searchable" : "Withdrawn from shared search") : document.published_id === currentApproval?.id && currentApproval ? "Published and searchable" : currentApproval?.built_at ? "New search version ready for owner activation" : currentApproval ? (currentApproval.indexing_attempts >= 3 ? "Indexing needs attention — not published" : "Approved; indexing before publication") : "Current file is not approved for shared search"}</p>
    {published ? <p>Shared search uses file version {publishedVersion?.number}, extraction revision {published.revision_id}. {published.version_id !== source.id ? "The replacement above is private until reviewed, approved and indexed." : null}</p> : null}
    {source.error ? <ErrorNotice message={source.error} /> : null}
    {source.warnings.length ? <details open><summary>Extraction warnings ({source.warnings.length})</summary><ul>{source.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></details> : null}
    {document.can_edit ? <>
      <LibraryDependencies document={document} />
      <LibraryOwnership document={document} dirty={dirty} />
      <div className="library-actions">
        <Button variant="secondary" type="submit" disabled={download.isPending} onClick={() => download.mutate()}>Download original for comparison</Button>
        {["failed", "cancelled"].includes(source.stage) ? <Button variant="primary" type="submit" disabled={mutation.isPending} onClick={() => mutation.mutate("retry")}>Retry processing</Button> : null}
        {["queued", "scanning", "extracting"].includes(source.stage) ? <Button variant="secondary" type="submit" disabled={mutation.isPending} onClick={() => mutation.mutate("cancellation")}>Cancel processing</Button> : null}
      </div>
      {source.stage === "ready_for_review" ? <Review key={revisionKey} document={document} refresh={refresh} onDirty={() => { setDirtyRevision(revisionKey); preview.reset(); }} /> : null}
      {document.review_fingerprint ? <section>
        {dirty ? <p role="status">You have unsaved passage changes. Save the extraction review before previewing or approving it.</p> : null}
        <Button variant="secondary" type="submit" disabled={dirty || preview.isPending} onClick={() => preview.mutate()}>Preview saved retrieval chunks</Button>
        {preview.isError ? <ErrorNotice message={errorMessage(preview.error)} /> : null}
        {preview.data ? <details open><summary>{preview.data.length} chunks from the saved review</summary>{preview.data.map(c => <article key={c.id} className="library-passage"><h4>{c.location} · exact passage · {c.token_count} budget units</h4><p dir="auto" className="library-text">{c.original_text}</p><RetrievalContext chunk={c} /></article>)}</details> : null}
        <h3>Approve shared publication</h3><p>Approval shares only the saved, selected passages with everyone in this workspace. It does not confirm applicability to other Requirements.</p>
        <Button variant="primary" type="submit" disabled={dirty || mutation.isPending || source.blocking_warnings.length > 0 || !!approval && !approval.withdrawn_at && (approval.fingerprint === document.review_fingerprint || approval.revision_id === source.revisions.at(-1)?.id || !approval.activated_at)} onClick={() => mutation.mutate("approve")}>Approve saved revision</Button>
      </section> : null}
      {document.build_fingerprint ? <CorpusBuild document={document} dirty={dirty} refresh={refresh} /> : null}
      {approval && !approval.activated_at && !approval.withdrawn_at && approval.indexing_attempts >= 3 ? <section><p>Indexing stopped after three attempts. Check provider availability before retrying.</p><Button variant="primary" type="submit" disabled={retryIndex.isPending} onClick={() => retryIndex.mutate()}>Retry indexing</Button>{retryIndex.isError ? <ErrorNotice message={errorMessage(retryIndex.error)} /> : null}</section> : null}
      {document.publications.some(p => !p.withdrawn_at) ? <section>
        <h3>Withdraw shared evidence</h3><label>Why is this evidence no longer safe to use?<input value={reason} onChange={e => setReason(e.target.value)} /></label>
        <Button variant="secondary" type="submit" disabled={mutation.isPending || !reason.trim()} onClick={() => mutation.mutate("withdraw")}>Withdraw from search now</Button>
      </section> : null}
      <details><summary>Version and review history</summary><ul>{document.versions.map(v => <li key={v.id}>Version {v.number}: {v.filename} · {v.revisions.length} extraction revisions · {v.checksum}</li>)}</ul></details>
      <section><h3>Upload a replacement</h3><p>The published version remains searchable until you review and approve this replacement and indexing finishes.</p>
        {dirty ? <p role="status">Save your passage changes before uploading a replacement. Your unsaved review stays on this page.</p> : null}
        <label>Replacement file<input type="file" onChange={e => { setReplacement(e.target.files?.[0] ?? null); setReplacementKey(crypto.randomUUID()); }} /></label>
        <Button variant="secondary" type="submit" disabled={dirty || !replacement || replaceFile.isPending} onClick={() => replaceFile.mutate()}>Upload new immutable version</Button>
        {replaceFile.isError ? <ErrorNotice message={errorMessage(replaceFile.error)} /> : null}
      </section>
    </> : <section aria-label="Published passages">{source.revisions[0]?.passages.map(p => <article key={p.block_id} id={`block-${p.block_id}`} className="library-passage"><h3>{source.blocks.find(b => b.id === p.block_id)?.label}</h3><p dir="auto" className="library-text">{p.text}</p></article>)}</section>}
    {mutation.isError || download.isError ? <ErrorNotice message={errorMessage(mutation.error ?? download.error)} /> : null}
  </div>;
}

function Citation({ document, params }: { document: LibraryDocument; params: URLSearchParams }) {
  const publication = document.publications.find(p => p.id === params.get("publication") && p.id === document.published_id && !p.withdrawn_at);
  const source = document.versions.find(v => v.id === params.get("version") && v.id === publication?.version_id);
  const revision = source?.revisions.find(r => r.id === params.get("revision") && r.id === publication?.revision_id);
  const passage = revision?.passages.find(p => p.block_id === params.get("passage") && p.included);
  const block = source?.blocks.find(b => b.id === passage?.block_id);
  return <section aria-label="Cited published passage">
    <h2 dir="auto">{document.title}</h2>
    {source && passage && block ? <>
      <p>Published file version {source.number} · extraction revision {revision!.id}</p>
      <h3 dir="auto">{block.section_path.join(" / ")} · {block.label}</h3>
      <p dir="auto" className="library-text">{passage.text}</p>
      <p>This is the approved passage, not the latest working extraction. Applicability still requires the Requirement owner's decision.</p>
    </> : <ErrorNotice message="This exact citation is no longer published or cannot be resolved. Search again for current evidence." />}
    <ButtonLink variant="secondary" to={`/documents/library/${document.id}`}>Open current document workspace</ButtonLink>
  </section>;
}

export function LibraryPage() {
  useDocumentTitle("Shared knowledge library");
  const { libraryId } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const cache = useQueryClient();
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submissionKey, setSubmissionKey] = useState(() => crypto.randomUUID());
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState("documents");
  const list = useQuery({ queryKey: queryKeys.scope("library"), queryFn: api.listLibrary });
  const detail = useQuery({ queryKey: queryKeys.scope("library", libraryId), queryFn: () => api.getLibraryDocument(libraryId!), enabled: !!libraryId,
    refetchInterval: q => q.state.data && pending(q.state.data) ? 1500 : false });
  const refresh = () => { search.reset(); unified.reset(); void cache.invalidateQueries({ queryKey: queryKeys.scope("library") }); };
  const upload = useMutation({ mutationFn: () => api.uploadLibrary(file!, title, submissionKey), onSuccess: d => { refresh(); setSubmissionKey(crypto.randomUUID()); navigate(`/documents/library/${d.id}`); } });
  const search = useMutation({ mutationFn: (text: string) => api.searchKnowledge(text) });
  const unified = useMutation({ mutationFn: (text: string) => api.searchUnifiedKnowledge(text) });
  const searching = search.isPending || unified.isPending;
  return <>
    <PageHeader title="Shared knowledge library" description="Review reference documents before sharing their passages. Uploaded content stays private until publication." actions={<ButtonLink to="/documents" variant="secondary">Requirement attachments</ButtonLink>} />
    {location.state?.ownershipTransferred ? <p role="status">Ownership transferred to {location.state.ownershipTransferred}. Your private access has ended.</p> : null}
    <div className="library-layout">
      <aside className="library-controls">
        <section><h2>Add a reference document</h2>
          <form onSubmit={e => { e.preventDefault(); upload.mutate(); }}>
            <label>Document title<input required maxLength={200} value={title} onChange={e => setTitle(e.target.value)} /></label>
            <label>Original file<input required type="file" accept=".pdf,.docx,.xlsx,.pptx,.csv,.tsv,.txt,.md,.png,.jpg,.jpeg" onChange={e => { setFile(e.target.files?.[0] ?? null); setSubmissionKey(crypto.randomUUID()); }} /></label>
            <Button variant="primary" type="submit" disabled={upload.isPending || !file || !title.trim()}>{upload.isPending ? "Uploading…" : "Upload for private review"}</Button>
          </form>
          {upload.isError ? <ErrorNotice message={errorMessage(upload.error)} /> : null}
        </section>
        <section><h2>Find knowledge</h2><form onSubmit={e => { e.preventDefault(); search.reset(); unified.reset(); if (scope === "all") unified.mutate(query); else search.mutate(query); }}>
          <label>Search in<select value={scope} onChange={e => { setScope(e.target.value); search.reset(); unified.reset(); }}><option value="documents">Published documents</option><option value="all">Requirements and documents</option></select></label>
          <label>Search text<input dir="auto" value={query} onChange={e => { setQuery(e.target.value); search.reset(); unified.reset(); }} maxLength={2000} required /></label>
          <Button variant="secondary" type="submit" disabled={searching || !query.trim()}>{searching ? "Searching…" : scope === "all" ? "Search knowledge" : "Search published passages"}</Button>
        </form>{search.isError ? <ErrorNotice message={errorMessage(search.error)} /> : unified.isError ? <ErrorNotice message={errorMessage(unified.error)} /> : null}
        {scope === "all" ? <p>Search published passages and Requirements you own or review. Source labels distinguish author input from approved documents.</p> : null}
        </section>
        <section><h2>Your documents and published references</h2>
          {list.isPending ? <LoadingState label="Loading library" variant="row" /> : list.isError ? <ErrorNotice message={errorMessage(list.error)} /> : <ul className="library-list">{list.data.map(d => <li key={d.id}><Link dir="auto" to={`/documents/library/${d.id}`}>{d.title}</Link><small>{d.can_edit ? "Owned by you" : "Published reference"}</small></li>)}</ul>}
          {list.data?.length === 0 ? <p>No documents yet. Upload a reference to begin.</p> : null}
        </section>
      </aside>
      <div>
        {scope === "all" && unified.data && unified.variables === query ? <section aria-label="Unified search results"><h2>Knowledge search results</h2>{unified.data.length === 0 ? <p>No current evidence matched.</p> : unified.data.map((hit, i) => { const c = hit.reference_evidence; return <article className="library-passage" key={`${hit.source_type}-${hit.source_id}-${i}`}>
          <p><strong>{c ? "Published document" : "Requirement evidence"}</strong></p>
          <Link dir="auto" to={c ? `/documents/library/${encodeURIComponent(c.document_id)}?${new URLSearchParams({ publication: c.publication_id, version: c.version_id, revision: c.revision_id, passage: c.block_id })}` : hit.evidence_path}>{hit.title}{c ? ` · version ${c.version_number} · ${c.location}` : ""}</Link>
          <p dir="auto" className="library-text">{hit.excerpt}</p>
          {c ? <p>Publication does not confirm applicability to your Requirement.</p> : null}
        </article>; })}</section> : null}
        {scope === "documents" && search.data && search.variables === query ? <section aria-label="Search results"><h2>Published search results</h2>{search.data.length === 0 ? <p>No published passages matched.</p> : search.data.map(c => <article className="library-passage" key={c.id}>
          <Link to={`/documents/library/${c.document_id}?${new URLSearchParams({ publication: c.publication_id, version: c.version_id, revision: c.revision_id, passage: c.block_id })}`}>{c.document_title} · version {c.version_number} · {c.location}</Link><p><strong>Exact citable passage</strong></p><p dir="auto" className="library-text">{c.original_text}</p><RetrievalContext chunk={c} />
        </article>)}</section> : null}
        {detail.isError ? <ErrorNotice message={errorMessage(detail.error)} /> : detail.data ? params.has("publication") ? <Citation document={detail.data} params={params} /> : <Detail key={detail.data.id} document={detail.data} refresh={refresh} /> : libraryId ? <LoadingState label="Opening reference document" variant="panel" /> : <section><h2>Evidence, with an explicit owner decision</h2><p>Choose a document to review its extraction, or search approved passages. References inform a Requirement; its owner still decides whether they apply.</p></section>}
      </div>
    </div>
  </>;
}
