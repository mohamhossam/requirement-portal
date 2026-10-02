import { Plus, Trash2 } from "lucide-react";
import { useId, useState, type FormEvent, type ReactNode } from "react";

import type { System } from "../../api/knowledge";
import { newId, type Person, type Product, type Squad, type SquadSystem, type ValueStream } from "../../api/organisation";
import { ErrorNotice } from "../../components/ErrorNotice";
import {
  Button,
  Checkbox,
  Input,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  Select,
  Textarea,
} from "../../components/ui";

type DialogProps<T> = {
  initial: T | null;
  saving: boolean;
  error: string | null;
  onSave: (record: T) => void;
  onCancel: () => void;
};

function EditorDialog({ title, description, saving, error, onSubmit, onCancel, children, wide = false }: {
  title: string;
  description?: string;
  saving: boolean;
  error: string | null;
  onSubmit: () => void;
  onCancel: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const titleId = useId();
  const submit = (event: FormEvent) => { event.preventDefault(); onSubmit(); };
  return (
    <Modal variant="dialog" size={wide ? "wide" : "md"} labelledBy={titleId} onClose={onCancel}>
      <form onSubmit={submit}>
        <ModalHeader id={titleId} title={title} description={description} />
        <ModalBody>
          {children}
          {error && <ErrorNotice message={error} />}
        </ModalBody>
        <ModalFooter>
          <Button onClick={onCancel}>Cancel</Button>
          <Button type="submit" variant="primary" loading={saving} loadingLabel="Saving…">Save</Button>
        </ModalFooter>
      </form>
    </Modal>
  );
}

function PersonSelect({ label, value, people, onChange, hint, placeholder = "Not named yet" }: {
  label: string;
  value: string | null | undefined;
  people: Person[];
  onChange: (value: string | null) => void;
  hint?: string;
  placeholder?: string;
}) {
  const choices = people.filter((person) => person.active || person.id === value);
  return (
    <Select label={label} hint={hint} value={value ?? ""} onChange={(event) => onChange(event.target.value || null)}>
      <option value="">{placeholder}</option>
      {choices.map((person) => (
        <option key={person.id} value={person.id}>{person.name}{person.team ? ` · ${person.team}` : ""}</option>
      ))}
    </Select>
  );
}

export function PersonDialog({ initial, taken, ...props }: DialogProps<Person> & { taken: string[] }) {
  const [name, setName] = useState(initial?.name ?? "");
  const [team, setTeam] = useState(initial?.team ?? "");
  const [email, setEmail] = useState(initial?.email ?? "");
  const [active, setActive] = useState(initial?.active ?? true);
  return (
    <EditorDialog
      {...props}
      title={initial ? `Edit ${initial.name}` : "Add a person"}
      description="People are shared across value streams and squads."
      onSubmit={() => props.onSave({
        id: initial?.id ?? newId(name, taken),
        name: name.trim(),
        team: team.trim() || null,
        email: email.trim() || null,
        active,
        revision: initial?.revision ?? 1,
      })}
    >
      <Input label="Name" required value={name} onChange={(event) => setName(event.target.value)} />
      <Input label="Team" hint="The team this person comes from." placeholder="Example: CRM platform team"
        value={team} onChange={(event) => setTeam(event.target.value)} />
      <Input label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
      {initial && (
        <Checkbox label="Active" hint="Inactive people cannot be named as leads, scrum masters or resources."
          checked={active} onChange={(event) => setActive(event.target.checked)} />
      )}
    </EditorDialog>
  );
}

export function ValueStreamDialog({ initial, taken, people, ...props }: DialogProps<ValueStream> & {
  taken: string[];
  people: Person[];
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [lead, setLead] = useState<string | null>(initial?.lead_person_id ?? null);
  return (
    <EditorDialog
      {...props}
      title={initial ? `Edit ${initial.name}` : "Add a value stream"}
      onSubmit={() => props.onSave({
        id: initial?.id ?? newId(name, taken),
        name: name.trim(),
        lead_person_id: lead,
        revision: initial?.revision ?? 1,
      })}
    >
      <Input label="Value stream name" required placeholder="Example: Retail sales" value={name}
        onChange={(event) => setName(event.target.value)} />
      <PersonSelect label="Value stream lead" value={lead} people={people} onChange={setLead}
        hint="Add people on the People tab first." />
    </EditorDialog>
  );
}

function SystemPicker({ systems, selected, onToggle }: {
  systems: System[];
  selected: Set<string>;
  onToggle: (id: string) => void;
}) {
  const [search, setSearch] = useState("");
  const needle = search.trim().toLowerCase();
  const shown = systems.filter((system) => !needle || `${system.name} ${system.id}`.toLowerCase().includes(needle));
  return (
    <fieldset className="border-line grid gap-2 rounded-md border border-solid p-3">
      <legend className="text-label text-ink px-1">Systems ({selected.size} chosen)</legend>
      <Input label="Filter systems" type="search" value={search}
        onChange={(event) => setSearch(event.target.value)} />
      <div className="grid max-h-60 gap-1 overflow-y-auto">
        {shown.map((system) => (
          <Checkbox key={system.id} label={system.name} checked={selected.has(system.id)}
            onChange={() => onToggle(system.id)} />
        ))}
        {shown.length === 0 && <p className="text-meta text-ink-muted m-0">No system matches.</p>}
      </div>
    </fieldset>
  );
}

export function ProductDialog({ initial, taken, valueStreamId, systems, ...props }: DialogProps<Product> & {
  taken: string[];
  valueStreamId: string;
  systems: System[];
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [selected, setSelected] = useState(new Set(initial?.system_ids ?? []));
  const toggle = (id: string) => setSelected((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  return (
    <EditorDialog
      {...props}
      wide
      title={initial ? `Edit ${initial.name}` : "Add a product"}
      description="Link the architecture systems this product is made of."
      onSubmit={() => props.onSave({
        id: initial?.id ?? newId(name, taken),
        value_stream_id: initial?.value_stream_id ?? valueStreamId,
        name: name.trim(),
        description: description.trim(),
        system_ids: [...selected],
        revision: initial?.revision ?? 1,
      })}
    >
      <Input label="Product name" required value={name} onChange={(event) => setName(event.target.value)} />
      <Textarea label="Description" rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
      <SystemPicker systems={systems} selected={selected} onToggle={toggle} />
    </EditorDialog>
  );
}

export function SquadDialog({ initial, taken, valueStreamId, systems, people, ...props }: DialogProps<Squad> & {
  taken: string[];
  valueStreamId: string;
  systems: System[];
  people: Person[];
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [scrumMaster, setScrumMaster] = useState<string | null>(initial?.scrum_master_person_id ?? null);
  const [rows, setRows] = useState<SquadSystem[]>(initial?.systems ?? []);
  const catalogued = new Map(systems.map((system) => [system.id, system.name]));
  const update = (index: number, changes: Partial<SquadSystem>) =>
    setRows((current) => current.map((row, position) => (position === index ? { ...row, ...changes } : row)));
  const available = (index: number) => systems.filter((system) =>
    !rows.some((row, position) => position !== index && row.system_id === system.id));
  return (
    <EditorDialog
      {...props}
      wide
      title={initial ? `Edit ${initial.name}` : "Add a squad"}
      description="Name one resource from each system the squad works on. They can come from different teams."
      onSubmit={() => props.onSave({
        id: initial?.id ?? newId(name, taken),
        name: name.trim(),
        value_stream_id: initial?.value_stream_id ?? valueStreamId,
        scrum_master_person_id: scrumMaster,
        systems: rows.filter((row) => row.system_id),
        revision: initial?.revision ?? 1,
      })}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label="Squad name" required value={name} onChange={(event) => setName(event.target.value)} />
        <PersonSelect label="Scrum master" value={scrumMaster} people={people} onChange={setScrumMaster} />
      </div>
      <fieldset className="border-line grid gap-3 rounded-md border border-solid p-3">
        <legend className="text-label text-ink px-1">Systems and their resources</legend>
        {rows.length === 0 && <p className="text-meta text-ink-muted m-0">No systems yet.</p>}
        {rows.map((row, index) => (
          <div key={index} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
            <Select label={`System ${index + 1}`} required value={row.system_id}
              onChange={(event) => update(index, { system_id: event.target.value })}>
              <option value="">Choose a system…</option>
              {row.system_id && !catalogued.has(row.system_id) && (
                <option value={row.system_id}>{row.system_id} (not in the catalogue in use)</option>
              )}
              {available(index).map((system) => <option key={system.id} value={system.id}>{system.name}</option>)}
            </Select>
            <PersonSelect label={`Resource for system ${index + 1}`} value={row.person_id} people={people}
              onChange={(value) => update(index, { person_id: value })} />
            <Button variant="ghost" icon={<Trash2 size={14} aria-hidden="true" />}
              aria-label={`Remove system ${index + 1} from the squad`}
              onClick={() => setRows((current) => current.filter((_, position) => position !== index))}>
              Remove
            </Button>
          </div>
        ))}
        <Button size="sm" className="w-fit" icon={<Plus size={14} aria-hidden="true" />}
          onClick={() => setRows((current) => [...current, { system_id: "", person_id: null }])}>
          Add system
        </Button>
      </fieldset>
    </EditorDialog>
  );
}
