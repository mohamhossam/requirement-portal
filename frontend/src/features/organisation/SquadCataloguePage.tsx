import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, Pencil, Plus, Search, Trash2, UserPlus, UsersRound } from "lucide-react";
import { useState } from "react";

import { errorMessage } from "../../api/errors";
import { knowledgeApi, type System } from "../../api/knowledge";
import {
  organisationApi,
  type Organisation,
  type Person,
  type Product,
  type Squad,
  type ValueStream,
} from "../../api/organisation";
import { SEARCH_FRAME, SEARCH_INPUT } from "../../app/dashboard/controls";
import { useDocumentTitle } from "../../app/useDocumentTitle";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import { PageHeader } from "../../components/shell";
import { AsyncState, LoadingState, asyncStatus } from "../../components/states";
import {
  Badge,
  Button,
  Card,
  Tab,
  TabList,
  TabPanel,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Tabs,
  cx,
} from "../../components/ui";
import { CatalogueNav } from "../catalogue/CatalogueNav";
import { catalogueKeys } from "../catalogue/keys";
import { PersonDialog, ProductDialog, SquadDialog, ValueStreamDialog } from "./editors";

type Editing =
  | { kind: "person"; record: Person | null }
  | { kind: "stream"; record: ValueStream | null }
  | { kind: "product"; record: Product | null; streamId: string }
  | { kind: "squad"; record: Squad | null; streamId: string };

type Removing = { kind: "stream" | "product" | "squad"; id: string; name: string; revision: number };

function Missing({ children }: { children: string }) {
  return <Badge tone="warning">{children}</Badge>;
}

function StreamCard({ stream, organisation, systems, editable, onEdit, onRemove }: {
  stream: ValueStream;
  organisation: Organisation;
  systems: Map<string, System>;
  editable: boolean;
  onEdit: (editing: Editing) => void;
  onRemove: (removing: Removing) => void;
}) {
  const people = new Map(organisation.people.map((person) => [person.id, person]));
  const products = organisation.products.filter((item) => item.value_stream_id === stream.id);
  const squads = organisation.squads.filter((item) => item.value_stream_id === stream.id);
  const lead = stream.lead_person_id ? people.get(stream.lead_person_id) : undefined;
  const systemName = (id: string) => systems.get(id)?.name;
  const headingId = `stream-${stream.id}`;

  return (
    <Card as="article" padding="fluid" aria-labelledby={headingId} className="grid gap-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <p className="text-label text-ink-muted m-0">Value stream</p>
          <h2 className="text-headline text-ink m-0" id={headingId}>{stream.name}</h2>
          <p className="text-body text-ink-soft m-0 flex flex-wrap items-center gap-2">
            Lead: {lead ? <strong className="text-ink">{lead.name}</strong> : <Missing>Lead not named</Missing>}
          </p>
        </div>
        {editable && (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="ghost" icon={<Pencil size={14} aria-hidden="true" />}
              onClick={() => onEdit({ kind: "stream", record: stream })} aria-label={`Edit ${stream.name}`}>
              Edit
            </Button>
            <Button size="sm" variant="ghost" icon={<Trash2 size={14} aria-hidden="true" />}
              onClick={() => onRemove({ kind: "stream", id: stream.id, name: stream.name, revision: stream.revision })}
              aria-label={`Remove ${stream.name}`}>
              Remove
            </Button>
          </div>
        )}
      </header>

      <section className="grid gap-3" aria-labelledby={`${headingId}-products`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-title text-ink m-0" id={`${headingId}-products`}>Products ({products.length})</h3>
          {editable && (
            <Button size="sm" icon={<Plus size={14} aria-hidden="true" />}
              onClick={() => onEdit({ kind: "product", record: null, streamId: stream.id })}>
              Add product
            </Button>
          )}
        </div>
        {products.length === 0 ? (
          <p className="text-body text-ink-muted m-0">No products yet.</p>
        ) : (
          <ul className="m-0 grid list-none gap-2 p-0 sm:grid-cols-2">
            {products.map((product) => (
              <li key={product.id} className="border-line bg-surface-sunken grid content-start gap-1.5 rounded-md border border-solid p-3">
                <div className="flex items-start justify-between gap-2">
                  <strong className="text-body text-ink">{product.name}</strong>
                  {editable && (
                    <div className="flex gap-1">
                      <Button size="icon" variant="ghost" aria-label={`Edit ${product.name}`}
                        onClick={() => onEdit({ kind: "product", record: product, streamId: stream.id })}>
                        <Pencil size={14} aria-hidden="true" />
                      </Button>
                      <Button size="icon" variant="ghost" aria-label={`Remove ${product.name}`}
                        onClick={() => onRemove({ kind: "product", id: product.id, name: product.name, revision: product.revision })}>
                        <Trash2 size={14} aria-hidden="true" />
                      </Button>
                    </div>
                  )}
                </div>
                {product.description && <p className="text-meta text-ink-soft m-0">{product.description}</p>}
                <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0" aria-label={`Systems in ${product.name}`}>
                  {product.system_ids.map((id) => (
                    <li key={id} className={cx("text-meta rounded-sm px-2 py-0.5", systemName(id) ? "bg-surface text-ink-soft" : "bg-warning-wash text-warning")}>
                      {systemName(id) ?? `${id} (not in the catalogue in use)`}
                    </li>
                  ))}
                  {product.system_ids.length === 0 && <li className="text-meta text-ink-muted">No systems linked</li>}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="grid gap-3" aria-labelledby={`${headingId}-squads`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-title text-ink m-0" id={`${headingId}-squads`}>Squads ({squads.length})</h3>
          {editable && (
            <Button size="sm" icon={<Plus size={14} aria-hidden="true" />}
              onClick={() => onEdit({ kind: "squad", record: null, streamId: stream.id })}>
              Add squad
            </Button>
          )}
        </div>
        {squads.length === 0 && <p className="text-body text-ink-muted m-0">No squads yet.</p>}
        {squads.map((squad) => {
          const scrumMaster = squad.scrum_master_person_id ? people.get(squad.scrum_master_person_id) : undefined;
          return (
            <section key={squad.id} className="grid gap-2" aria-label={squad.name}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <h4 className="text-body text-ink m-0 font-semibold">{squad.name}</h4>
                  <span className="text-meta text-ink-soft flex items-center gap-1.5">
                    Scrum master: {scrumMaster ? scrumMaster.name : <Missing>Not named</Missing>}
                  </span>
                </div>
                {editable && (
                  <div className="flex gap-1">
                    <Button size="sm" variant="ghost" icon={<Pencil size={14} aria-hidden="true" />}
                      onClick={() => onEdit({ kind: "squad", record: squad, streamId: stream.id })}
                      aria-label={`Edit ${squad.name}`}>
                      Edit
                    </Button>
                    <Button size="sm" variant="ghost" icon={<Trash2 size={14} aria-hidden="true" />}
                      onClick={() => onRemove({ kind: "squad", id: squad.id, name: squad.name, revision: squad.revision })}
                      aria-label={`Remove ${squad.name}`}>
                      Remove
                    </Button>
                  </div>
                )}
              </div>
              <Table caption={`Systems and resources in ${squad.name}`}>
                <TableHead>
                  <tr>
                    <TableHeaderCell>System</TableHeaderCell>
                    <TableHeaderCell>Resource</TableHeaderCell>
                    <TableHeaderCell>From team</TableHeaderCell>
                  </tr>
                </TableHead>
                <TableBody columns={3} empty={squad.systems.length === 0 ? "No systems in this squad yet." : undefined}>
                  {squad.systems.map((row) => {
                    const person = row.person_id ? people.get(row.person_id) : undefined;
                    return (
                      <TableRow key={row.system_id}>
                        <TableCell>
                          {systemName(row.system_id) ?? <span className="flex flex-wrap items-center gap-2">{row.system_id}<Missing>Not in the catalogue in use</Missing></span>}
                        </TableCell>
                        <TableCell>{person ? person.name : <Missing>Resource needed</Missing>}</TableCell>
                        <TableCell>{person?.team ?? "—"}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </section>
          );
        })}
      </section>
    </Card>
  );
}

function PeopleTable({ organisation, editable, onEdit }: {
  organisation: Organisation;
  editable: boolean;
  onEdit: (editing: Editing) => void;
}) {
  const [search, setSearch] = useState("");
  const needle = search.trim().toLowerCase();
  const roles = (person: Person) => {
    const result: string[] = [];
    organisation.value_streams.filter((item) => item.lead_person_id === person.id)
      .forEach((item) => result.push(`Leads ${item.name}`));
    organisation.squads.filter((item) => item.scrum_master_person_id === person.id)
      .forEach((item) => result.push(`Scrum master of ${item.name}`));
    const systems = organisation.squads.flatMap((item) => item.systems).filter((row) => row.person_id === person.id).length;
    if (systems) result.push(`Resource on ${systems} squad system${systems === 1 ? "" : "s"}`);
    return result;
  };
  const people = organisation.people
    .filter((person) => !needle || `${person.name} ${person.team ?? ""}`.toLowerCase().includes(needle))
    .sort((a, b) => a.name.localeCompare(b.name));
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className={cx(SEARCH_FRAME, "max-w-md")}>
          <Search className="text-ink-muted shrink-0" size={16} aria-hidden="true" />
          <span className="sr-only">Search people</span>
          <input className={SEARCH_INPUT} type="search" value={search} placeholder="Search by name or team"
            onChange={(event) => setSearch(event.target.value)} />
        </label>
        {editable && (
          <Button variant="primary" icon={<UserPlus size={16} aria-hidden="true" />}
            onClick={() => onEdit({ kind: "person", record: null })}>
            Add person
          </Button>
        )}
      </div>
      <Table caption={`People (${organisation.people.length})`}>
        <TableHead>
          <tr>
            <TableHeaderCell>Name</TableHeaderCell>
            <TableHeaderCell>Team</TableHeaderCell>
            <TableHeaderCell>Roles</TableHeaderCell>
            {editable && <TableHeaderCell align="end"><span className="sr-only">Actions</span></TableHeaderCell>}
          </tr>
        </TableHead>
        <TableBody columns={editable ? 4 : 3} empty={organisation.people.length === 0
          ? "No people yet. Add the leads, scrum masters and system resources."
          : people.length === 0 ? "No one matches the search." : undefined}>
          {people.map((person) => (
            <TableRow key={person.id}>
              <TableCell>
                <span className="text-ink">{person.name}</span>
                {!person.active && <> <Badge>Inactive</Badge></>}
                {person.email && <span className="text-meta text-ink-muted block">{person.email}</span>}
              </TableCell>
              <TableCell>{person.team ?? "—"}</TableCell>
              <TableCell>
                {roles(person).length
                  ? <ul className="text-meta m-0 grid gap-0.5 pl-4">{roles(person).map((role) => <li key={role}>{role}</li>)}</ul>
                  : <span className="text-meta text-ink-muted">No role yet</span>}
              </TableCell>
              {editable && (
                <TableCell className="text-right">
                  <Button size="sm" variant="ghost" onClick={() => onEdit({ kind: "person", record: person })}
                    aria-label={`Edit ${person.name}`}>
                    Edit
                  </Button>
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

/**
 * Who works on what. Value streams are led by one person, manage products made
 * of architecture systems, and own squads; each squad has a scrum master and
 * one resource per system it works on. Edited in place: no versions to publish.
 */
export function SquadCataloguePage() {
  useDocumentTitle("Squad catalogue");
  const client = useQueryClient();
  const me = useQuery({ queryKey: catalogueKeys.me, queryFn: knowledgeApi.me });
  const roles: string[] = me.data?.roles ?? [];
  const editable = roles.includes("knowledge_maintainer");
  const reader = editable || roles.includes("knowledge_reader");
  const organisation = useQuery({ queryKey: catalogueKeys.organisation, queryFn: organisationApi.get, enabled: reader });
  const active = useQuery({ queryKey: catalogueKeys.active, queryFn: knowledgeApi.active, enabled: reader });
  const [editing, setEditing] = useState<Editing | null>(null);
  const [removing, setRemoving] = useState<Removing | null>(null);
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState("");
  const done = (message: string) => (data: Organisation) => {
    client.setQueryData(catalogueKeys.organisation, data);
    setEditing(null);
    setRemoving(null);
    setNotice(message);
  };
  const save = useMutation({
    mutationFn: async (change: Editing & { value: Person | ValueStream | Product | Squad }) => {
      const revision = change.record ? change.record.revision : undefined;
      if (change.kind === "person") return organisationApi.savePerson(change.value as Person, revision);
      if (change.kind === "stream") return organisationApi.saveValueStream(change.value as ValueStream, revision);
      if (change.kind === "product") return organisationApi.saveProduct(change.value as Product, revision);
      return organisationApi.saveSquad(change.value as Squad, revision);
    },
    onSuccess: (data, change) => done(`${change.value.name} saved.`)(data),
  });
  const remove = useMutation({
    mutationFn: ({ kind, id, revision }: Removing) => kind === "stream"
      ? organisationApi.removeValueStream(id, revision)
      : kind === "product" ? organisationApi.removeProduct(id, revision) : organisationApi.removeSquad(id, revision),
    onSuccess: (data, removed) => done(`${removed.name} removed.`)(data),
  });
  const open = (next: Editing) => { save.reset(); setEditing(next); };

  if (me.isPending) return <LoadingState label="Checking your access" variant="page" />;
  const header = (
    <PageHeader
      eyebrow="Documents"
      title="Squad catalogue"
      description="Value streams, the products they manage, and their squads: a scrum master and one resource from each system the squad works on."
      actions={editable && (
        <Button variant="primary" icon={<Plus size={16} aria-hidden="true" />} onClick={() => open({ kind: "stream", record: null })}>
          Add value stream
        </Button>
      )}
    />
  );
  if (!reader) {
    return <>{header}<CatalogueNav />
      <p className="text-body text-ink-soft m-0">Viewing the squad catalogue needs the knowledge reader role. Ask an administrator for access.</p>
    </>;
  }

  const data = organisation.data ?? { people: [], value_streams: [], products: [], squads: [] };
  const systems = new Map((active.data?.systems ?? []).map((system) => [system.id, system]));
  const systemList = [...systems.values()].sort((a, b) => a.name.localeCompare(b.name));
  const needle = search.trim().toLowerCase();
  const streams = data.value_streams
    .filter((stream) => !needle || [stream.name,
      ...data.squads.filter((item) => item.value_stream_id === stream.id).map((item) => item.name),
      ...data.products.filter((item) => item.value_stream_id === stream.id).map((item) => item.name)]
      .some((value) => value.toLowerCase().includes(needle)))
    .sort((a, b) => a.name.localeCompare(b.name));
  const dialogProps = {
    saving: save.isPending,
    error: save.error ? errorMessage(save.error) : null,
    onCancel: () => setEditing(null),
  };

  return (
    <>
      {header}
      <CatalogueNav />
      {!editable && <p className="text-meta text-ink-muted mt-0 mb-4">You can view the squad catalogue; maintainers edit it.</p>}
      {remove.error && <ErrorNotice message={errorMessage(remove.error)} />}
      {notice && <p className="text-body text-ink-soft mt-0 mb-4" role="status">{notice}</p>}
      <AsyncState
        status={asyncStatus(organisation)}
        loading={{ label: "Loading the squad catalogue", variant: "panel" }}
        error={{ title: "We couldn’t load the squad catalogue", message: errorMessage(organisation.error) }}
        onRetry={() => void organisation.refetch()}
        headingLevel="h2"
      >
        <Tabs defaultValue="streams">
          <TabList label="Squad catalogue sections">
            <Tab value="streams" icon={<Layers size={16} aria-hidden="true" />} count={data.value_streams.length}>
              Value streams
            </Tab>
            <Tab value="people" icon={<UsersRound size={16} aria-hidden="true" />} count={data.people.length}>
              People
            </Tab>
          </TabList>
          <TabPanel value="streams" className="grid gap-5 pt-5">
            {data.value_streams.length > 0 && (
              <label className={cx(SEARCH_FRAME, "max-w-md")}>
                <Search className="text-ink-muted shrink-0" size={16} aria-hidden="true" />
                <span className="sr-only">Search value streams, products and squads</span>
                <input className={SEARCH_INPUT} type="search" value={search}
                  placeholder="Search value streams, products or squads" onChange={(event) => setSearch(event.target.value)} />
              </label>
            )}
            {data.value_streams.length === 0 && (
              <Card as="section" padding="fluid" className="grid gap-2" aria-labelledby="no-streams">
                <h2 className="text-title text-ink m-0" id="no-streams">No value streams yet</h2>
                <p className="text-body text-ink-soft m-0 max-w-[var(--measure-interface)]">
                  Add the people first, then a value stream with its lead. Inside it, add the products it manages and its
                  squads, each with a scrum master and one resource per system.
                </p>
              </Card>
            )}
            {streams.map((stream) => (
              <StreamCard key={stream.id} stream={stream} organisation={data} systems={systems} editable={editable}
                onEdit={open} onRemove={setRemoving} />
            ))}
            {data.value_streams.length > 0 && streams.length === 0 && (
              <p className="text-body text-ink-muted m-0">Nothing matches the search.</p>
            )}
          </TabPanel>
          <TabPanel value="people" className="pt-5">
            <PeopleTable organisation={data} editable={editable} onEdit={open} />
          </TabPanel>
        </Tabs>
      </AsyncState>

      {editing?.kind === "person" && (
        <PersonDialog {...dialogProps} initial={editing.record} taken={data.people.map((item) => item.id)}
          onSave={(value) => save.mutate({ ...editing, value })} />
      )}
      {editing?.kind === "stream" && (
        <ValueStreamDialog {...dialogProps} initial={editing.record} people={data.people}
          taken={data.value_streams.map((item) => item.id)} onSave={(value) => save.mutate({ ...editing, value })} />
      )}
      {editing?.kind === "product" && (
        <ProductDialog {...dialogProps} initial={editing.record} valueStreamId={editing.streamId} systems={systemList}
          taken={data.products.map((item) => item.id)} onSave={(value) => save.mutate({ ...editing, value })} />
      )}
      {editing?.kind === "squad" && (
        <SquadDialog {...dialogProps} initial={editing.record} valueStreamId={editing.streamId} systems={systemList}
          people={data.people} taken={data.squads.map((item) => item.id)}
          onSave={(value) => save.mutate({ ...editing, value })} />
      )}
      {removing && (
        <ConfirmDialog
          title={`Remove ${removing.name}?`}
          message={removing.kind === "stream"
            ? "Only an empty value stream can be removed; move or remove its products and squads first."
            : "Requirement mappings made from now on will no longer show it."}
          confirmLabel="Remove"
          onCancel={() => setRemoving(null)}
          onConfirm={() => remove.mutate(removing)}
        />
      )}
    </>
  );
}
