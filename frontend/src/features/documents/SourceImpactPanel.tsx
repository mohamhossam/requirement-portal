import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { Link } from "react-router-dom";

import { api, type DependencyImpact } from "../../api/client";
import { errorMessage } from "../../api/errors";
import { queryKeys } from "../../app/queryKeys";
import { Button } from "../../components/ui";
import "./source-impact.css";
import { ErrorNotice, LoadingState } from "../../components/states";

export function SourceImpactPanel({ documentId, requirementId, canDecide = false }: {
  documentId?: string; requirementId?: string; canDecide?: boolean;
}) {
  const heading = useId();
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const [activeOnly, setActiveOnly] = useState(true);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const result = useQuery({
    queryKey: queryKeys.scope("source-impact", documentId, requirementId, offset, activeOnly, search),
    queryFn: () => api.sourceImpact({ documentId, requirementId, offset, activeOnly, query: search }),
    enabled: open,
  });
  return <section className="source-impact" aria-labelledby={heading}>
    <h3 id={heading}>Source lineage and change impact</h3>
    <p>Follow recorded citations into answers, analyses and backlog content. Only Requirements you can access appear here.</p>
    <Button aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? "Hide source impact" : "Review source impact"}</Button>
    {open ? <>
      <form className="source-impact-actions" onSubmit={event => { event.preventDefault(); setSearch(query.trim()); setOffset(0); }}>
        <label>Find affected content<input value={query} onChange={event => setQuery(event.target.value)} maxLength={200} /></label>
        <Button type="submit">Find dependencies</Button>
      </form>
      <label className="source-impact-checkbox"><input type="checkbox" checked={activeOnly} onChange={event => { setActiveOnly(event.target.checked); setOffset(0); }} />Active content only</label>
      <Button disabled={result.isFetching} onClick={() => { void result.refetch(); }}>Refresh source impact</Button>
      {result.isPending ? <LoadingState label="Loading source impact" variant="row" /> : result.isError ? <ErrorNotice message={errorMessage(result.error)} /> : <>
        {result.data.items.length ? result.data.items.map(item => <ImpactRow key={`${item.dependency.id}:${item.publication_state}`} item={item} canDecide={canDecide} />) : <p>No recorded dependencies match this view.</p>}
        <nav className="source-impact-actions" aria-label="Source impact pages">
          <Button disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 20))}>Previous impact page</Button>
          <span>Page {Math.floor(offset / 20) + 1}</span>
          <Button disabled={result.data.next_offset === null} onClick={() => setOffset(result.data.next_offset!)}>Next impact page</Button>
        </nav>
      </>}
    </> : null}
  </section>;
}

function ImpactRow({ item, canDecide }: { item: DependencyImpact; canDecide: boolean }) {
  const [reason, setReason] = useState("");
  const [decision, setDecision] = useState<"retain_historical" | "revise_content">("revise_content");
  const cache = useQueryClient();
  const row = item.dependency;
  const citation = row.lineage.citation;
  const mutation = useMutation({
    mutationFn: () => api.decideSourceImpact(item, decision, reason),
    onSuccess: async () => {
      setReason("");
      await Promise.all([
        queryKeys.scope("source-impact"), queryKeys.analysis(row.requirement_id),
        queryKeys.requirement(row.requirement_id), queryKeys.breakdownReview(row.requirement_id),
        queryKeys.approvalWorkflow(row.requirement_id),
      ].map(queryKey => cache.invalidateQueries({ queryKey })));
    },
  });
  return <article className="source-impact-row" aria-label={`${row.target_kind} source dependency`}>
    <Link to={`/requirements/${row.requirement_id}/clarify`} dir="auto">{row.requirement_title}</Link>
    <p>{row.target_kind === "clarification" ? "Clarification answer" : row.target_kind.charAt(0).toUpperCase() + row.target_kind.slice(1)} · {row.lineage.via.length ? "Indirect dependency" : "Direct citation"} · {row.current ? "Current content" : "Historical content"}</p>
    <p className="source-impact-text" dir="auto">{row.statement}</p>
    <p>{citation.title} · Version {citation.version_number} · {citation.location}</p>
    <p>{item.publication_current ? "Cited publication is current" : !row.active ? "Historical dependency — no active content" : item.needs_review ? "Publication changed — review required" : "Historical evidence — review recorded"}</p>
    <details><summary>Exact source and lineage</summary>
      <blockquote dir="auto" className="source-impact-text">{citation.excerpt}</blockquote>
      <p className="source-impact-text">Publication: {citation.publication_id}<br />File version: {citation.version_id}<br />Extraction revision: {citation.revision_id}<br />Passage: {citation.block_id} · Characters {citation.start_offset}–{citation.end_offset}</p>
      {row.lineage.via.length ? <><p>This content used the following inputs. This does not assert direct support for every sentence.</p><ol>{row.lineage.via.map((step, index) => <li key={`${index}:${step}`} className="source-impact-text">{step}</li>)}</ol></> : null}
    </details>
    {item.decisions.length ? <details><summary>Impact review history</summary><ol>{item.decisions.map(record => <li key={record.version}>
      {record.decision === "retain_historical" ? "Retain historical evidence" : "Revise affected content"} · {record.actor.display_name} · {new Date(record.recorded_at).toLocaleString()}
      <p dir="auto">{record.reason}</p>
    </li>)}</ol></details> : null}
    {row.active && !item.publication_current ? canDecide ? <form onSubmit={event => { event.preventDefault(); if (reason.trim() && !mutation.isPending) mutation.mutate(); }}>
      <label>Impact decision<select value={decision} onChange={event => setDecision(event.target.value as typeof decision)}>
        <option value="revise_content">Revise affected content</option>
        <option value="retain_historical">Retain historical evidence for this content</option>
      </select></label>
      <p>{decision === "revise_content" ? "This stays unresolved until the affected content is revised or regenerated. Earlier decisions and approvals remain in history." : "Record why this exact historical source still applies. Later content or publication changes require another review."}</p>
      <label>Reason for impact decision<textarea required maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} rows={2} /></label>
      <Button type="submit" disabled={!reason.trim() || mutation.isPending}>{mutation.isPending ? "Saving review…" : "Record impact decision"}</Button>
      {mutation.isError ? <ErrorNotice message={errorMessage(mutation.error)} /> : null}
      {mutation.isSuccess ? <p role="status">Impact decision recorded.</p> : null}
    </form> : <p>The Requirement owner can record a decision in its <Link to={`/requirements/${row.requirement_id}/clarify`}>source impact review</Link>.</p> : null}
  </article>;
}
