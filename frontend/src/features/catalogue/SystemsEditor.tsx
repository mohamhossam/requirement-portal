import { useMutation } from "@tanstack/react-query";
import { Info, Layers, Plus, Search, Trash2 } from "lucide-react";
import { useState } from "react";

import { errorMessage } from "../../api/errors";
import {
  knowledgeApi, type KnowledgeRelease, type RelationshipKind, type System,
} from "../../api/knowledge";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import {
  Badge,
  Button,
  Input,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  cx,
  type SortDirection,
} from "../../components/ui";
import { SEARCH_FRAME, SEARCH_INPUT } from "../../app/dashboard/controls";
import { RELATIONSHIP_KINDS, RELATIONSHIP_KIND_LABEL, domainPath } from "./labels";
import { SystemDrawer } from "./SystemDrawer";

const EMPTY: System = {
  id: "", name: "", name_ar: null, aliases: [], capabilities: [], constraints: [], components: [],
};

/** The first two domains a system works in, and how many more. */
function DomainBadges({ names }: { names: string[] }) {
  if (names.length === 0) return <span className="text-meta text-ink-muted">None</span>;
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      {names.slice(0, 2).map((name) => <Badge key={name} icon={<Layers size={12} aria-hidden="true" />}>{name}</Badge>)}
      {names.length > 2 && (
        <span className="text-meta text-ink-muted">
          <span aria-hidden="true">+{names.length - 2} more</span>
          <span className="sr-only">and {names.slice(2).join(", ")}</span>
        </span>
      )}
    </span>
  );
}

/** Direct edits to the draft's systems and the dependencies between them. */
export function SystemsEditor({ draft, onChanged }: { draft: KnowledgeRelease; onChanged: () => void }) {
  const [search, setSearch] = useState("");
  const [direction, setDirection] = useState<SortDirection>("asc");
  const [editing, setEditing] = useState<{ system: System; creating: boolean } | null>(null);
  const [retiring, setRetiring] = useState<System | null>(null);
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState<RelationshipKind>("unspecified");
  const [status, setStatus] = useState("");
  const save = useMutation({
    mutationFn: knowledgeApi.save,
    onSuccess: (_, release) => {
      setEditing(null);
      setRetiring(null);
      setStatus(release.relationships.length !== draft.relationships.length
        ? "Dependencies saved." : "Version saved.");
      onChanged();
    },
  });
  const names = new Map(draft.systems.map((system) => [system.id, system.name]));
  const domains = draft.capability_domains ?? [];
  // The business domains a system works in, through its capabilities, by name.
  const domainsOf = (system: System) => [...new Set(system.capabilities.map((item) => item.domain_id).filter(Boolean))]
    .map((id) => domainPath(domains, id).at(-1)?.name)
    .filter((name): name is string => Boolean(name));
  const needle = search.trim().toLowerCase();
  const systems = draft.systems
    .filter((system) => !needle || [system.id, system.name, system.name_ar ?? "", ...system.aliases]
      .some((value) => value.toLowerCase().includes(needle)))
    .sort((a, b) => (direction === "asc" ? 1 : -1) * a.name.localeCompare(b.name));

  const saveSystem = (system: System) => save.mutate({
    ...draft,
    systems: editing?.creating
      ? [...draft.systems, system]
      : draft.systems.map((item) => (item.id === system.id ? system : item)),
  });

  return (
    <section className="grid min-w-0 gap-6" aria-labelledby="systems-editor-title">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid gap-1">
          <h3 className="text-title text-ink m-0" id="systems-editor-title">Edit manually</h3>
          <p className="text-meta text-ink-muted m-0">Change this version’s systems and dependencies directly.</p>
        </div>
        <Button variant="primary" icon={<Plus size={16} aria-hidden="true" />}
          onClick={() => { save.reset(); setEditing({ system: EMPTY, creating: true }); }}>
          Add system
        </Button>
      </header>
      {save.error && !editing && <ErrorNotice message={errorMessage(save.error)} />}
      {status && <p className="text-meta text-ink-soft m-0" role="status">{status}</p>}
      {domains.length === 0 && draft.systems.length > 0 && (
        <div className="border-line bg-accent-wash text-body text-ink-soft flex items-start gap-2 rounded-sm border border-solid border-l-[3px] border-l-[var(--accent)] px-3 py-2">
          <Info className="text-accent mt-0.5 shrink-0" size={16} aria-hidden="true" />
          <p className="m-0">
            This version has no capability domains, so capabilities can’t be placed in a business area.{" "}
            <Button variant="text" className="px-0" onClick={() => {
              const heading = document.getElementById("domains-title");
              heading?.scrollIntoView({ block: "start" });
              heading?.focus({ preventScroll: true });
            }}>
              Add domains
            </Button>
            {" "}below, or upload a catalogue file that includes them.
          </p>
        </div>
      )}

      <div className="grid gap-3">
        <label className={cx(SEARCH_FRAME, "max-w-md")}>
          <Search className="text-ink-muted shrink-0" size={16} aria-hidden="true" />
          <span className="sr-only">Search systems</span>
          <input className={SEARCH_INPUT} type="search" value={search} placeholder="Search by name, ID or other name"
            onChange={(event) => setSearch(event.target.value)} />
        </label>
        <Table caption={`Systems in this version (${draft.systems.length})`}>
          <TableHead>
            <tr>
              <TableHeaderCell sort={direction} onSort={() => setDirection(direction === "asc" ? "desc" : "asc")}>
                System
              </TableHeaderCell>
              <TableHeaderCell>Domains</TableHeaderCell>
              <TableHeaderCell>Components</TableHeaderCell>
              <TableHeaderCell>Capabilities</TableHeaderCell>
              <TableHeaderCell>Constraints</TableHeaderCell>
              <TableHeaderCell align="end"><span className="sr-only">Actions</span></TableHeaderCell>
            </tr>
          </TableHead>
          <TableBody columns={6} empty={draft.systems.length === 0
            ? "No systems yet. Add one, build from documents, or upload a catalogue file."
            : systems.length === 0 ? "No system matches the search." : undefined}>
            {systems.map((system) => (
              <TableRow key={system.id} interactive>
                <TableCell>
                  <button type="button" className="text-body text-ink cursor-pointer border-0 bg-transparent p-0 text-left font-semibold underline-offset-2 hover:underline"
                    onClick={() => { save.reset(); setEditing({ system, creating: false }); }}>
                    {system.name}
                  </button>
                  <span className="text-meta text-ink-muted block font-mono">{system.id}</span>
                </TableCell>
                <TableCell><DomainBadges names={domainsOf(system)} /></TableCell>
                <TableCell numeric>{system.components?.length ?? 0}</TableCell>
                <TableCell numeric>{system.capabilities.length}</TableCell>
                <TableCell numeric>{system.constraints.length}</TableCell>
                <TableCell className="text-right">
                  <Button size="sm" variant="ghost" icon={<Trash2 size={14} aria-hidden="true" />}
                    onClick={() => setRetiring(system)} aria-label={`Remove ${system.name}`}>
                    Remove
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <section className="grid gap-3" aria-labelledby="dependencies-title">
        <h4 className="text-body text-ink m-0 font-semibold" id="dependencies-title">
          Dependencies ({draft.relationships.length})
        </h4>
        {draft.relationships.length === 0 ? (
          <p className="text-body text-ink-muted m-0">No dependencies between systems yet.</p>
        ) : (
          <ul className="border-line m-0 grid list-none rounded-md border border-solid p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">
            {draft.relationships.map((relationship, index) => (
              <li key={`${relationship.source_system_id}-${relationship.target_system_id}-${relationship.description}`}
                className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                <span className="text-body text-ink-soft min-w-0 flex-1">
                  <strong className="text-ink">{names.get(relationship.source_system_id) ?? relationship.source_system_id}</strong>
                  {" → "}
                  <strong className="text-ink">{names.get(relationship.target_system_id) ?? relationship.target_system_id}</strong>
                  {`: ${relationship.description}`}
                </span>
                <Select fieldClassName="w-44" disabled={save.isPending} value={relationship.kind ?? "unspecified"}
                  label={<span className="sr-only">
                    How {names.get(relationship.source_system_id) ?? relationship.source_system_id} depends
                    on {names.get(relationship.target_system_id) ?? relationship.target_system_id}
                  </span>}
                  onChange={(event) => save.mutate({ ...draft, relationships: draft.relationships.map((item, position) =>
                    position === index ? { ...item, kind: event.target.value as RelationshipKind } : item) })}>
                  {RELATIONSHIP_KINDS.map((kind) => <option key={kind} value={kind}>{RELATIONSHIP_KIND_LABEL[kind]}</option>)}
                </Select>
                <Button size="sm" variant="ghost" disabled={save.isPending}
                  aria-label={`Remove dependency ${names.get(relationship.source_system_id) ?? relationship.source_system_id} → ${names.get(relationship.target_system_id) ?? relationship.target_system_id}`}
                  onClick={() => save.mutate({ ...draft, relationships: draft.relationships.filter((_, position) => position !== index) })}>
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}
        <form className="grid gap-3 sm:grid-cols-2 sm:items-end lg:grid-cols-[1fr_1fr_2fr_1fr_auto]" onSubmit={(event) => {
          event.preventDefault();
          // Cleared only once saved: a rejected save keeps what was typed so it can be retried.
          save.mutate({ ...draft, relationships: [...draft.relationships,
            { source_system_id: source, target_system_id: target, description: description.trim(), kind }] }, {
            onSuccess: () => {
              setDescription("");
              setKind("unspecified");
            },
          });
        }}>
          <Select label="From system" required value={source} onChange={(event) => setSource(event.target.value)}>
            <option value="">Choose…</option>
            {draft.systems.map((system) => <option key={system.id} value={system.id}>{system.name}</option>)}
          </Select>
          <Select label="Depends on" required value={target} onChange={(event) => setTarget(event.target.value)}>
            <option value="">Choose…</option>
            {draft.systems.filter((system) => system.id !== source)
              .map((system) => <option key={system.id} value={system.id}>{system.name}</option>)}
          </Select>
          <Input label="For what" required placeholder="Example: Reads customer accounts" value={description}
            onChange={(event) => setDescription(event.target.value)} />
          <Select label="How" value={kind} onChange={(event) => setKind(event.target.value as RelationshipKind)}>
            {RELATIONSHIP_KINDS.map((item) => <option key={item} value={item}>{RELATIONSHIP_KIND_LABEL[item]}</option>)}
          </Select>
          <Button type="submit" loading={save.isPending} loadingLabel="Saving…">Add dependency</Button>
        </form>
      </section>

      {editing && (
        <SystemDrawer
          initial={editing.system}
          domains={domains}
          landscape={draft.landscape_domains ?? []}
          creating={editing.creating}
          saving={save.isPending}
          error={save.error ? errorMessage(save.error) : null}
          onSave={saveSystem}
          onCancel={() => setEditing(null)}
        />
      )}
      {retiring && (
        <ConfirmDialog
          title={`Remove ${retiring.name}?`}
          message="Its components, capabilities, constraints and dependencies leave this version too. The published catalogue is not affected until you publish."
          confirmLabel="Remove system"
          onCancel={() => setRetiring(null)}
          onConfirm={() => save.mutate({
            ...draft,
            systems: draft.systems.filter((item) => item.id !== retiring.id),
            relationships: draft.relationships.filter((item) =>
              item.source_system_id !== retiring.id && item.target_system_id !== retiring.id),
          })}
        />
      )}
    </section>
  );
}
