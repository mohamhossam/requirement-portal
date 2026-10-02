import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, type LibraryDocument } from "../api/client";
import { errorMessage } from "../api/errors";
import { ErrorNotice, LoadingState } from "../components/states";
import { SourceImpactPanel } from "../features/documents/SourceImpactPanel";
import { queryKeys } from "./queryKeys";
import { Button } from "../components/ui/Button";

export function LibraryDependencies({ document }: { document: LibraryDocument }) {
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const dependencies = useQuery({
    queryKey: queryKeys.scope("library", document.id, "dependencies", document.version, offset),
    queryFn: () => api.libraryDependencies(document.id, offset), enabled: open,
  });
  return <section aria-labelledby="dependencies-heading">
    <SourceImpactPanel documentId={document.id} />
    <h3 id="dependencies-heading">Requirements using this document</h3>
    <p>Check references before replacing or withdrawing evidence. Only Requirements you own or review appear here; this is not a complete workspace impact count.</p>
    <Button variant="secondary" type="submit" aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? "Hide dependencies" : "View dependencies"}</Button>
    {open ? <>
      <p>Accepted and edited references can inform backlog generation. Pending proposals still need a decision; rejected and historical proposals are retained for traceability.</p>
      <Button variant="secondary" type="submit" disabled={dependencies.isFetching} onClick={() => { void dependencies.refetch(); }}>Refresh dependencies</Button>
      {dependencies.isPending ? <LoadingState label="Loading document dependencies" variant="row" /> : dependencies.isError ? <ErrorNotice message={errorMessage(dependencies.error)} /> : <>
        {dependencies.data.items.length === 0 ? <p>No recorded references on this page in Requirements you can access.</p> : dependencies.data.items.map((item, index) => <article className="library-passage" key={`${item.analysis_id}:${item.proposal_id}:${index}`}>
          <Link to={`/requirements/${item.requirement_id}/clarify`} dir="auto">{item.requirement_title}</Link>
          <p>{item.current_analysis ? "Current analysis" : "Historical analysis"} · Round {item.round_number ?? "unavailable"} · {item.status === "edited" ? "Accepted with edits" : item.status === "accepted" ? "Accepted" : item.status === "rejected" ? "Rejected" : "Pending decision"}</p>
          <p dir="auto" className="library-text">{item.statement}</p>
          <p>{item.publication_current ? "Cited publication is current" : "Cited publication was withdrawn or replaced"} · File version {item.citation.version_number} · {item.citation.location}</p>
          <details><summary>Recorded citation</summary><p dir="auto" className="library-text">{item.citation.excerpt}</p>
            <p className="library-text">Publication: {item.citation.publication_id}<br />Extraction revision: {item.citation.revision_id}</p>
          </details>
          {item.current_analysis && item.status !== "rejected" && !item.publication_current ? <p>Reconcile this reference in the Requirement before continuing approval or generation.</p> : null}
        </article>)}
        <nav className="library-actions" aria-label="Dependency pages">
          <Button variant="secondary" type="submit" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 20))}>Previous dependencies</Button>
          <span>Page {Math.floor(offset / 20) + 1}</span>
          <Button variant="secondary" type="submit" disabled={dependencies.data.next_offset === null} onClick={() => setOffset(dependencies.data.next_offset!)}>Next dependencies</Button>
        </nav>
      </>}
    </> : null}
  </section>;
}

export function LibraryOwnership({ document, dirty }: { document: LibraryDocument; dirty: boolean }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const cache = useQueryClient();
  const navigate = useNavigate();
  const actors = useQuery({ queryKey: queryKeys.scope("library-actors", query), queryFn: () => api.searchActors(query), enabled: open });
  const history = useQuery({ queryKey: queryKeys.scope("library", document.id, "ownership", document.version), queryFn: () => api.libraryOwnershipHistory(document.id), enabled: open });
  const validTarget = actors.isSuccess && actors.data.some(actor => actor.id === target && actor.id !== document.owner.id.value);
  const transfer = useMutation({
    mutationFn: () => api.transferLibraryOwnership(document, target, reason),
    onSuccess: async receipt => {
      await cache.cancelQueries({ queryKey: queryKeys.scope("library") });
      cache.removeQueries({ queryKey: queryKeys.scope("library") });
      navigate("/documents/library", { replace: true, state: { ownershipTransferred: receipt.new_owner.display_name } });
    },
  });
  return <section aria-labelledby="ownership-heading">
    <h3 id="ownership-heading">Document ownership</h3>
    <Button variant="secondary" type="submit" aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? "Hide ownership controls" : "Manage ownership"}</Button>
    {open ? <>
      <p>The new owner receives all private files, reviews and publication controls. Uploaded-by and approved-by records stay unchanged.</p>
      {dirty ? <p role="status">Save your passage changes before transferring ownership.</p> : null}
      <form onSubmit={event => { event.preventDefault(); if (!dirty && validTarget && reason.trim() && acknowledged && !transfer.isPending) transfer.mutate(); }}>
        <label>Find a workspace user<input value={query} onChange={event => { setQuery(event.target.value); setTarget(""); setAcknowledged(false); }} maxLength={200} /></label>
        {actors.isPending ? <LoadingState label="Loading known users" variant="row" /> : actors.isError ? <ErrorNotice message={errorMessage(actors.error)} /> : <label>New document owner<select required value={target} onChange={event => { setTarget(event.target.value); setAcknowledged(false); }}>
          <option value="">Choose a known user</option>
          {actors.data.filter(actor => actor.id !== document.owner.id.value).map(actor => <option key={actor.id} value={actor.id}>{actor.display_name}{actor.email ? ` (${actor.email})` : ""}</option>)}
        </select></label>}
        <label>Reason for ownership transfer<textarea required value={reason} onChange={event => setReason(event.target.value)} maxLength={2000} rows={2} /></label>
        <label className="library-checkbox"><input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} />I understand that I will lose private access and management of this document.</label>
        <Button variant="secondary" type="submit" disabled={dirty || !validTarget || !reason.trim() || !acknowledged || transfer.isPending}>{transfer.isPending ? "Transferring…" : "Transfer ownership"}</Button>
      </form>
      {transfer.isError ? <ErrorNotice message={errorMessage(transfer.error)} /> : null}
      <h4>Ownership history</h4>
      {history.isPending ? <LoadingState label="Loading ownership history" variant="row" /> : history.isError ? <ErrorNotice message={errorMessage(history.error)} /> : history.data.length ? <ul>{history.data.map((change, index) => <li key={index}>
        {change.previous_owner.display_name} → {change.new_owner.display_name} · {new Date(change.recorded_at).toLocaleString()}
        <p dir="auto">{change.reason}</p><p>Transferred by {change.performed_by.display_name}</p>
      </li>)}</ul> : <p>No ownership transfers recorded.</p>}
    </> : null}
  </section>;
}
