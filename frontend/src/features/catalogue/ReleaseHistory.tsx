import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, History, Trash2 } from "lucide-react";
import { useId, useState } from "react";

import { errorMessage } from "../../api/errors";
import { knowledgeApi, type CatalogueFileFormat, type KnowledgeRelease } from "../../api/knowledge";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Skeleton } from "../../components/Skeleton";
import {
  Badge,
  Button,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Textarea,
} from "../../components/ui";
import { catalogueKeys } from "./keys";
import { AUDIT_LABEL, formatTime, versionName } from "./labels";

function statusOf(release: KnowledgeRelease, activeId: string | undefined) {
  if (release.id === activeId) return <Badge tone="success">In use</Badge>;
  return release.status === "draft" ? <Badge tone="warning">In progress</Badge> : <Badge>Published earlier</Badge>;
}

function Audit({ releaseId }: { releaseId: string }) {
  const audit = useQuery({ queryKey: catalogueKeys.audit(releaseId), queryFn: () => knowledgeApi.audit(releaseId) });
  if (audit.isPending) return <Skeleton label="Loading the change history" bars={2} />;
  if (audit.error) return <ErrorNotice message={errorMessage(audit.error)} />;
  if (audit.data.length === 0) return <p className="text-meta text-ink-muted m-0">No recorded changes.</p>;
  return (
    <ol className="text-meta text-ink-soft m-0 grid gap-1 pl-5">
      {audit.data.map((event, index) => (
        <li key={`${event.action}-${event.created_at}-${index}`}>
          {AUDIT_LABEL[event.action] ?? "Changed the catalogue"} · {event.actor_id} · {formatTime(event.created_at)}
          {event.rationale && <span className="block text-ink">“{event.rationale}”</span>}
        </li>
      ))}
    </ol>
  );
}

/** Every version, which one is in use, and the ways back to an earlier one. */
export function ReleaseHistory({
  releases,
  activeId,
  onChanged,
  onRemoved,
}: {
  releases: KnowledgeRelease[];
  activeId: string | undefined;
  onChanged: () => void;
  /** Called after a version in progress was removed. */
  onRemoved?: (release: KnowledgeRelease) => void;
}) {
  const titleId = useId();
  const [open, setOpen] = useState<string | null>(null);
  const [format, setFormat] = useState<CatalogueFileFormat>("xlsx");
  const [reactivating, setReactivating] = useState<KnowledgeRelease | null>(null);
  const [rationale, setRationale] = useState("");
  const exportFile = useMutation({
    mutationFn: ({ id, as }: { id: string; as: CatalogueFileFormat }) => knowledgeApi.exportFile(id, as),
  });
  const [removing, setRemoving] = useState<KnowledgeRelease | null>(null);
  const [removed, setRemoved] = useState("");
  const discard = useMutation({
    mutationFn: (release: KnowledgeRelease) => knowledgeApi.discard(release),
    onSuccess: (_, release) => {
      setRemoved(`“${versionName(release)}” was removed.`);
      onRemoved?.(release);
      onChanged();
    },
  });
  const activate = useMutation({
    mutationFn: ({ release, why }: { release: KnowledgeRelease; why: string }) => knowledgeApi.activate(release, why),
    onSuccess: () => { setReactivating(null); setRationale(""); onChanged(); },
  });

  return (
    <section className="grid gap-3" aria-labelledby={titleId}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid gap-1">
          <h2 className="text-headline text-ink m-0 flex items-center gap-2" id={titleId}>
            <History size={18} aria-hidden="true" /> Versions
          </h2>
          <p className="text-meta text-ink-muted m-0">
            Download any version, make an earlier one active again, or remove a version still in progress.
          </p>
        </div>
        <Select label="Download format" value={format} fieldClassName="w-44"
          onChange={(event) => setFormat(event.target.value as CatalogueFileFormat)}>
          <option value="xlsx">Excel (.xlsx)</option>
          <option value="yaml">YAML</option>
          <option value="json">JSON</option>
        </Select>
      </div>
      {(exportFile.error || activate.error || discard.error) && (
        <ErrorNotice message={errorMessage(exportFile.error ?? activate.error ?? discard.error)} />
      )}
      {removed && <p className="text-meta text-ink-soft m-0" role="status">{removed}</p>}
      <Table caption="Catalogue versions">
        <TableHead>
          <tr>
            <TableHeaderCell>Version</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell>Published</TableHeaderCell>
            <TableHeaderCell>Systems</TableHeaderCell>
            <TableHeaderCell align="end"><span className="sr-only">Actions</span></TableHeaderCell>
          </tr>
        </TableHead>
        <TableBody columns={5} empty={releases.length === 0 ? "No versions yet." : undefined}>
          {releases.flatMap((release) => {
            const expanded = open === release.id;
            return [
              <TableRow key={release.id}>
                <TableCell>
                  <div className="grid">
                    <span className="text-body text-ink break-words">{versionName(release)}</span>
                    {release.name && <span className="font-mono text-meta text-ink-muted block max-w-[14rem] truncate" title={release.id}>{release.id}</span>}
                  </div>
                </TableCell>
                <TableCell>{statusOf(release, activeId)}</TableCell>
                <TableCell>
                  {release.published_at ? (
                    <div className="grid">
                      <span className="whitespace-nowrap">{formatTime(release.published_at)}</span>
                      <span className="text-meta text-ink-muted">by {release.published_by}</span>
                    </div>
                  ) : "Not yet"}
                </TableCell>
                <TableCell numeric>{release.systems.length}</TableCell>
                <TableCell>
                  <div className="grid grid-cols-[repeat(3,max-content)] items-center justify-end gap-1">
                    <Button size="sm" variant="ghost" icon={<Download size={14} aria-hidden="true" />}
                      loading={exportFile.isPending && exportFile.variables?.id === release.id} loadingLabel="Preparing…"
                      onClick={() => exportFile.mutate({ id: release.id, as: format })}
                      aria-label={`Download ${versionName(release)} as ${format.toUpperCase()}`}>
                      Download
                    </Button>
                    <Button size="sm" variant="ghost" aria-expanded={expanded}
                      onClick={() => setOpen(expanded ? null : release.id)}>
                      {expanded ? "Hide log" : "Change log"}
                    </Button>
                    {release.status === "published" && release.id !== activeId && (
                      <Button size="sm" onClick={() => setReactivating(release)}>Make active again</Button>
                    )}
                    {release.status === "published" && release.id === activeId && <span aria-hidden="true" />}
                    {release.status === "draft" && (
                      <Button size="sm" variant="ghost" icon={<Trash2 size={14} aria-hidden="true" />}
                        loading={discard.isPending && discard.variables?.id === release.id} loadingLabel="Removing…"
                        onClick={() => { discard.reset(); setRemoved(""); setRemoving(release); }}
                        aria-label={`Remove ${versionName(release)}`}>
                        Remove
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>,
              expanded && (
                <TableRow key={`${release.id}-audit`}>
                  <TableCell colSpan={5}><Audit releaseId={release.id} /></TableCell>
                </TableRow>
              ),
            ];
          })}
        </TableBody>
      </Table>
      {removing && (
        <ConfirmDialog
          title={`Remove “${versionName(removing)}”?`}
          message="Its changes, source-document list, AI suggestions and evidence index are deleted. Published versions and the version in use are not affected. This cannot be undone."
          confirmLabel="Remove version"
          onCancel={() => setRemoving(null)}
          onConfirm={() => { const release = removing; setRemoving(null); discard.mutate(release); }}
        />
      )}
      {reactivating && (
        <Modal variant="dialog" labelledBy={`${titleId}-reactivate`} onClose={() => setReactivating(null)}>
          <form onSubmit={(event) => { event.preventDefault(); activate.mutate({ release: reactivating, why: rationale }); }}>
            <ModalHeader id={`${titleId}-reactivate`} title={`Make “${versionName(reactivating)}” active again?`}
              description="Requirement mapping switches back to it straight away." />
            <ModalBody>
              <Textarea label="Why go back to this version?" required rows={3} value={rationale}
                onChange={(event) => setRationale(event.target.value)} />
              {activate.error && <ErrorNotice message={errorMessage(activate.error)} />}
            </ModalBody>
            <ModalFooter>
              <Button onClick={() => setReactivating(null)}>Cancel</Button>
              <Button type="submit" variant="primary" loading={activate.isPending} loadingLabel="Switching…">
                Make active
              </Button>
            </ModalFooter>
          </form>
        </Modal>
      )}
    </section>
  );
}
