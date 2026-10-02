import { Boxes, ChevronRight, Layers, Lock, Plus, Trash2, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";

import type { Capability, CapabilityDomain, Component, LandscapeDomain, System } from "../../api/knowledge";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import {
  Badge, Button, Input, Modal, ModalFooter, ModalHeader, Select, TagInput, Textarea, cx, withDraft,
} from "../../components/ui";
import { domainLabel, domainTree, slug } from "./labels";

/**
 * One capability while it is being edited. `key` is stable across reorders and
 * removals so React keeps each card's focus and open state with the right row.
 * `fresh` marks a capability added in this drawer: its ID follows its name
 * until someone types one.
 */
type CapabilityForm = {
  key: number;
  id: string;
  name: string;
  triggers: string[];
  draft: string;
  domain_id: string;
  /** The key of the component row that delivers it, so editing that component's ID keeps the link. */
  component: number | null;
  fresh: boolean;
  idTouched: boolean;
  open: boolean;
};

/** One component while it is being edited (ADR-0092); keyed like a capability. */
type ComponentForm = {
  key: number;
  id: string;
  name: string;
  name_ar: string;
  aliases: string[];
  draft: string;
  technology: string;
  description: string;
  fresh: boolean;
  idTouched: boolean;
  open: boolean;
};

type ComponentErrors = Partial<Record<"id" | "name", string>>;
type CapabilityErrors = Partial<Record<"id" | "name" | "triggers", string>>;
type SystemErrors = Partial<Record<"id" | "name", string>>;
type ConstraintRow = { key: number; text: string };

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;
/** Indents a nested domain in a native select, where padding cannot reach. */
const INDENT = "    ";

/** The system as saved, so an unsaved change can be told from none. */
const normalise = (system: System): System => ({
  id: system.id,
  name: system.name,
  name_ar: system.name_ar,
  aliases: system.aliases,
  description: system.description ?? null,
  landscape_domain_id: system.landscape_domain_id ?? null,
  constraints: system.constraints,
  capabilities: system.capabilities.map((item) => ({
    id: item.id, name: item.name, triggers: item.triggers, domain_id: item.domain_id ?? null,
    component_id: item.component_id ?? null,
  })),
  components: (system.components ?? []).map((item) => ({
    id: item.id, name: item.name, name_ar: item.name_ar ?? null, aliases: item.aliases ?? [],
    technology: item.technology ?? null, description: item.description ?? null,
  })),
});

function Section({ id, title, description, children }: {
  id: string;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="grid gap-3">
      <header className="grid gap-1">
        <h3 className="text-title text-ink m-0" id={id}>{title}</h3>
        {description && <p className="text-meta text-ink-muted m-0 max-w-[64ch]">{description}</p>}
      </header>
      {children}
    </section>
  );
}

/**
 * Add or edit one system in a version in progress.
 *
 * Four parts, each a heading a person can jump to: who the system is, what it is
 * for and where it sits in the landscape, and the other names requirements use
 * for it; the components it is built from, what it
 * does (capabilities, each placed in a business domain and a component), and
 * what it must respect (constraints). Capabilities
 * fold to a one-line summary so a system with eight of them is still one
 * screen, and the header and the Save bar stay put while the middle scrolls.
 *
 * Closing with unsaved changes asks first: this drawer holds minutes of fiddly
 * work, and Escape is the easiest key in the room to press by accident.
 *
 * Only the form changes here: what is saved is the same `System` as before.
 */
export function SystemDrawer({
  initial,
  domains,
  landscape,
  creating,
  saving,
  error,
  onSave,
  onCancel,
}: {
  initial: System;
  domains: CapabilityDomain[];
  /** The version's landscape domains (ADR-0094), where the system can be placed. */
  landscape: LandscapeDomain[];
  creating: boolean;
  saving: boolean;
  error: string | null;
  onSave: (system: System) => void;
  onCancel: () => void;
}) {
  const base = useId();
  const titleId = `${base}-title`;
  const addCapabilityId = `${base}-add-capability`;
  const addComponentId = `${base}-add-component`;
  const addConstraintId = `${base}-add-constraint`;
  // Rows that arrive with the system are keyed by position; rows added here count on from there.
  const componentBase = initial.capabilities.length + initial.constraints.length;
  const nextKey = useRef(componentBase + (initial.components ?? []).length);
  const key = () => (nextKey.current += 1);

  const [id, setId] = useState(initial.id);
  const [idTouched, setIdTouched] = useState(!creating);
  const [name, setName] = useState(initial.name);
  const [nameAr, setNameAr] = useState(initial.name_ar ?? "");
  const [aliases, setAliases] = useState(initial.aliases);
  const [description, setDescription] = useState(initial.description ?? "");
  const [landscapeId, setLandscapeId] = useState(initial.landscape_domain_id ?? "");
  const [aliasDraft, setAliasDraft] = useState("");
  const [constraints, setConstraints] = useState<ConstraintRow[]>(
    () => initial.constraints.map((text, index) => ({ key: initial.capabilities.length + index, text })),
  );
  const [components, setComponents] = useState<ComponentForm[]>(() => (initial.components ?? []).map((item, index) => ({
    key: componentBase + index, id: item.id, name: item.name, name_ar: item.name_ar ?? "", aliases: item.aliases ?? [],
    draft: "", technology: item.technology ?? "", description: item.description ?? "",
    fresh: false, idTouched: true, open: false,
  })));
  const [capabilities, setCapabilities] = useState<CapabilityForm[]>(() => initial.capabilities.map((item, index) => ({
    key: index, id: item.id, name: item.name, triggers: item.triggers, draft: "", domain_id: item.domain_id ?? "",
    component: (initial.components ?? []).findIndex((part) => part.id === item.component_id) >= 0
      ? componentBase + (initial.components ?? []).findIndex((part) => part.id === item.component_id) : null,
    fresh: false, idTouched: true, open: false,
  })));
  const [componentErrors, setComponentErrors] = useState<Record<number, ComponentErrors>>({});
  const [systemErrors, setSystemErrors] = useState<SystemErrors>({});
  const [errors, setErrors] = useState<Record<number, CapabilityErrors>>({});
  const [announcement, setAnnouncement] = useState("");
  const [confirmingDiscard, setConfirmingDiscard] = useState(false);
  // A field to focus once it has rendered: a new row, the first one refused, or
  // the neighbour of a row just removed, so focus never falls back to the page.
  const focusNext = useRef<string | null>(null);
  const setFocusTarget = (target: string) => { focusNext.current = target; };

  useEffect(() => {
    if (!focusNext.current) return;
    document.getElementById(focusNext.current)?.focus();
    focusNext.current = null;
  });

  const fieldId = (capability: number, field: string) => `${base}-capability-${capability}-${field}`;
  const partId = (component: number, field: string) => `${base}-component-${component}-${field}`;
  const constraintId = (row: number) => `${base}-constraint-${row}`;

  const update = (target: number, changes: Partial<CapabilityForm>) =>
    setCapabilities((current) => current.map((item) => {
      if (item.key !== target) return item;
      const next = { ...item, ...changes };
      // A new capability's ID follows its name until someone types one.
      if (changes.name !== undefined && next.fresh && !next.idTouched) next.id = slug(changes.name, "");
      return next;
    }));
  const clearError = (target: number, field: keyof CapabilityErrors) =>
    setErrors((current) => (current[target]?.[field]
      ? { ...current, [target]: { ...current[target], [field]: undefined } } : current));

  const updateComponent = (target: number, changes: Partial<ComponentForm>) =>
    setComponents((current) => current.map((item) => {
      if (item.key !== target) return item;
      const next = { ...item, ...changes };
      if (changes.name !== undefined && next.fresh && !next.idTouched) next.id = slug(changes.name, "");
      return next;
    }));
  const clearComponentError = (target: number, field: keyof ComponentErrors) =>
    setComponentErrors((current) => (current[target]?.[field]
      ? { ...current, [target]: { ...current[target], [field]: undefined } } : current));
  const addComponent = () => {
    const added = key();
    setComponents((current) => [...current, {
      key: added, id: "", name: "", name_ar: "", aliases: [], draft: "", technology: "", description: "",
      fresh: true, idTouched: false, open: true,
    }]);
    setFocusTarget(partId(added, "name"));
  };
  const removeComponent = (index: number) => {
    const removed = components[index];
    if (!removed || capabilities.some((item) => item.component === removed.key)) return;
    const neighbour = components[index + 1] ?? components[index - 1];
    setComponents((current) => current.filter((item) => item.key !== removed.key));
    setFocusTarget(neighbour ? partId(neighbour.key, "toggle") : addComponentId);
    setAnnouncement(`Removed ${removed.name.trim() || "the new component"}. Cancel to keep it.`);
  };
  /** The capabilities a component row delivers, by name, so its card and Remove can say so. */
  const deliveredBy = (target: number) => capabilities.flatMap((item, index) =>
    item.component === target ? [item.name.trim() || `Capability ${index + 1}`] : []);

  const addCapability = () => {
    const added = key();
    setCapabilities((current) => [...current, {
      key: added, id: "", name: "", triggers: [], draft: "", domain_id: "", component: null,
      fresh: true, idTouched: false, open: true,
    }]);
    setFocusTarget(fieldId(added, "name"));
  };
  const removeCapability = (index: number) => {
    const removed = capabilities[index];
    if (!removed) return;
    const neighbour = capabilities[index + 1] ?? capabilities[index - 1];
    setCapabilities((current) => current.filter((item) => item.key !== removed.key));
    setFocusTarget(neighbour ? fieldId(neighbour.key, "toggle") : addCapabilityId);
    setAnnouncement(`Removed ${removed.name.trim() || "the new capability"}. Cancel to keep it.`);
  };
  const addConstraint = () => {
    const added = key();
    setConstraints((current) => [...current, { key: added, text: "" }]);
    setFocusTarget(constraintId(added));
  };
  const removeConstraint = (index: number) => {
    const removed = constraints[index];
    if (!removed) return;
    const neighbour = constraints[index + 1] ?? constraints[index - 1];
    setConstraints((current) => current.filter((item) => item.key !== removed.key));
    setFocusTarget(neighbour ? constraintId(neighbour.key) : addConstraintId);
    setAnnouncement(`Removed constraint ${index + 1}.`);
  };

  // A row with neither an ID nor a name was never started; it is dropped, as before.
  const started = capabilities.filter((item) => item.id.trim() || item.name.trim());
  const startedParts = components.filter((item) => item.id.trim() || item.name.trim());
  const partIds = new Map(startedParts.map((item) => [item.key, item.id.trim()]));
  const system = (): System => ({
    id: id.trim(),
    name: name.trim(),
    name_ar: nameAr.trim() || null,
    aliases: withDraft(aliases, aliasDraft),
    description: description.trim() || null,
    landscape_domain_id: landscapeId || null,
    constraints: constraints.map((row) => row.text.trim()).filter(Boolean),
    capabilities: started.map((item): Capability => ({
      id: item.id.trim(), name: item.name.trim(), triggers: withDraft(item.triggers, item.draft),
      domain_id: item.domain_id || null,
      component_id: (item.component !== null && partIds.get(item.component)) || null,
    })),
    components: startedParts.map((item): Component => ({
      id: item.id.trim(), name: item.name.trim(), name_ar: item.name_ar.trim() || null,
      aliases: withDraft(item.aliases, item.draft), technology: item.technology.trim() || null,
      description: item.description.trim() || null,
    })),
  });
  const dirty = JSON.stringify(system()) !== JSON.stringify(normalise(initial))
    || capabilities.length !== started.length || components.length !== startedParts.length
    || constraints.some((row) => !row.text.trim());
  const requestClose = () => (dirty ? setConfirmingDiscard(true) : onCancel());

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const own: SystemErrors = {};
    if (!name.trim()) own.name = "Give the system a name.";
    if (creating && !id.trim()) own.id = "Give the system an ID.";
    const refused: Record<number, CapabilityErrors> = {};
    for (const item of started) {
      const problems: CapabilityErrors = {};
      if (!item.name.trim()) problems.name = "Give the capability a name.";
      if (!item.id.trim()) problems.id = "Give the capability an ID.";
      if (withDraft(item.triggers, item.draft).length === 0) problems.triggers = "Add at least one matching phrase.";
      if (Object.keys(problems).length > 0) refused[item.key] = problems;
    }
    const refusedParts: Record<number, ComponentErrors> = {};
    for (const item of startedParts) {
      const problems: ComponentErrors = {};
      if (!item.name.trim()) problems.name = "Give the component a name.";
      if (!item.id.trim()) problems.id = "Give the component an ID.";
      if (Object.keys(problems).length > 0) refusedParts[item.key] = problems;
    }
    setSystemErrors(own);
    setErrors(refused);
    setComponentErrors(refusedParts);
    const first = started.find((item) => refused[item.key]);
    const firstPart = startedParts.find((item) => refusedParts[item.key]);
    if (own.name || own.id) {
      setFocusTarget(`${base}-${own.name ? "name" : "id"}`);
    } else if (firstPart) {
      setFocusTarget(partId(firstPart.key, refusedParts[firstPart.key]?.name ? "name" : "id"));
    } else if (first) {
      const problems = refused[first.key] ?? {};
      setFocusTarget(fieldId(first.key, problems.name ? "name" : problems.id ? "id" : "triggers"));
    }
    if (own.name || own.id || first || firstPart) {
      // Collapsed cards hide their fields, so open the ones at fault.
      setCapabilities((current) => current.map((item) => (refused[item.key] ? { ...item, open: true } : item)));
      setComponents((current) => current.map((item) => (refusedParts[item.key] ? { ...item, open: true } : item)));
      return;
    }
    onSave(system());
  };

  const noDomains = domains.length === 0;
  const tree = domainTree(domains);
  const placedIn = [...new Set(capabilities.map((item) => item.domain_id).filter(Boolean))]
    .map((domain) => domainLabel(domains, domain))
    .filter(Boolean);
  const unplaced = capabilities.filter((item) => !item.domain_id).length;
  const filledConstraints = constraints.filter((row) => row.text.trim()).length;
  const place = domainLabel(landscape, landscapeId);
  const summary = [
    place,
    components.length > 0 && plural(components.length, "component", "components"),
    plural(capabilities.length, "capability", "capabilities"),
    plural(filledConstraints, "constraint", "constraints"),
    placedIn.length > 0 && `${placedIn.length === 1 ? "Domain" : "Domains"}: ${placedIn.join(", ")}`,
  ].filter(Boolean).join(" · ");

  return (
    <Modal variant="drawer" side="right" size="lg" labelledBy={titleId} onClose={requestClose}
      closeOnOutsideClick={!dirty} className="[scroll-padding-top:8rem] [scroll-padding-bottom:6rem]">
      <form onSubmit={submit} noValidate className="grid min-h-full grid-rows-[auto_1fr_auto]">
        <div className="bg-surface-raised border-line sticky -top-6 z-[var(--z-sticky)] -mx-6 -mt-6 border-0 border-b border-solid px-6 pt-6">
          <div className="pr-10">
            <ModalHeader id={titleId} eyebrow={creating ? "New system" : "System"}
              title={creating ? "Add a system" : `Edit ${initial.name}`}
              description={<span className="text-meta">{summary}</span>} />
          </div>
          <Button size="icon" variant="ghost" className="absolute top-5 right-5" aria-label="Close"
            icon={<X size={18} aria-hidden="true" />} onClick={requestClose} />
        </div>

        <div className="text-body text-ink-soft grid content-start gap-6 py-6 [&>section+section]:[border-top:1px_solid_var(--line)] [&>section+section]:pt-6">
          <p className="sr-only" role="status">{announcement}</p>

          <Section id={`${base}-identity`} title="Identity">
            <div className="grid gap-4 sm:grid-cols-2">
              <Input id={`${base}-name`} label="Name" required value={name} autoComplete="off" error={systemErrors.name}
                onChange={(event) => {
                  setName(event.target.value);
                  setSystemErrors((current) => ({ ...current, name: undefined }));
                  if (creating && !idTouched) setId(slug(event.target.value, ""));
                }} />
              <Input label="Arabic name" dir="auto" value={nameAr} autoComplete="off"
                onChange={(event) => setNameAr(event.target.value)} />
            </div>
            {creating ? (
              <Input id={`${base}-id`} label="System ID" required className="font-mono" value={id} autoComplete="off"
                error={systemErrors.id}
                hint="Filled in from the name. A short, stable key such as bcrm; it cannot change once saved."
                onChange={(event) => {
                  setId(event.target.value);
                  setIdTouched(true);
                  setSystemErrors((current) => ({ ...current, id: undefined }));
                }} />
            ) : (
              <div className="grid gap-1">
                <span className="text-label text-ink">System ID</span>
                <p className="m-0 flex flex-wrap items-center gap-2">
                  <Lock className="text-ink-muted shrink-0" size={14} aria-hidden="true" />
                  <code className="text-body text-ink font-mono">{initial.id}</code>
                  <span className="text-meta text-ink-muted">Set when the system was added; it cannot change.</span>
                </p>
              </div>
            )}
            <TagInput label="Other names" values={aliases} onChange={setAliases} draft={aliasDraft}
              onDraftChange={setAliasDraft} dir="auto"
              hint="What people call it in requirements; matching uses these too. Press Enter after each."
              placeholder="Example: common BFF" />
            <Textarea label="Description" rows={2} dir="auto" value={description}
              hint="What the system is for, in a sentence or two."
              placeholder="Example: Central customer, account and order store."
              onChange={(event) => setDescription(event.target.value)} />
            <Select label="Landscape domain" value={landscapeId} disabled={landscape.length === 0}
              hint={landscape.length === 0
                ? "This version has no landscape domains yet. Save, then add them under Landscape domains below the systems list."
                : "Where the system sits in the architecture landscape, such as Customer, Assisted."}
              onChange={(event) => setLandscapeId(event.target.value)}>
              <option value="">Not placed yet</option>
              {domainTree(landscape).map(({ domain: item, depth }) => (
                <option key={item.id} value={item.id}>{INDENT.repeat(depth)}{item.name}</option>
              ))}
            </Select>
          </Section>

          <Section id={`${base}-components`} title={`Components (${components.length})`}
            description="The parts this system is built from, such as a module or service. Each capability can name the one that delivers it.">
            {components.length === 0 ? (
              <p className="text-body text-ink-muted m-0">No components. Add them if the system is built from named parts.</p>
            ) : (
              <ul role="list" className="m-0 grid list-none gap-2 p-0">
                {components.map((part, index) => {
                  const number = index + 1;
                  const panelId = partId(part.key, "panel");
                  const problems = componentErrors[part.key] ?? {};
                  const title = part.name.trim() || "New component";
                  const code = part.id.trim();
                  const held = deliveredBy(part.key);
                  const delivers = held.length === 0 ? "Delivers no capabilities yet"
                    : `Delivers ${plural(held.length, "capability", "capabilities")}`;
                  return (
                    <li key={part.key}
                      className={cx("bg-surface rounded-md border border-solid",
                        Object.values(problems).some(Boolean) ? "border-danger" : "border-line")}>
                      <div className="flex items-start gap-2 p-2">
                        <button type="button" id={partId(part.key, "toggle")}
                          aria-expanded={part.open} aria-controls={panelId}
                          aria-label={`Component ${number}: ${title}${code ? `, ID ${code}` : ""}${part.technology.trim() ? `, ${part.technology.trim()}` : ""}, ${delivers}`}
                          className="grid min-h-11 min-w-0 flex-1 cursor-pointer gap-1 rounded-sm border-0 bg-transparent px-2 py-1.5 text-left hover:[background-color:color-mix(in_srgb,var(--accent)_6%,var(--surface))]"
                          onClick={() => updateComponent(part.key, { open: !part.open })}>
                          <span className="flex min-w-0 items-center gap-2">
                            <ChevronRight size={16} aria-hidden="true"
                              className={cx("text-ink-muted shrink-0 transition-transform duration-[var(--motion-fast)] motion-reduce:transition-none",
                                part.open && "rotate-90")} />
                            <span className="text-body text-ink truncate font-semibold">{title}</span>
                            {code && <code className="text-meta text-ink-muted hidden truncate font-mono sm:inline">{code}</code>}
                          </span>
                          <span className="flex flex-wrap items-center gap-x-2 gap-y-1 pl-6">
                            {code && <code className="text-meta text-ink-muted font-mono sm:hidden">{code}</code>}
                            {part.technology.trim() && <span className="text-meta text-ink-soft">{part.technology.trim()}</span>}
                            <span className="text-meta text-ink-muted" id={partId(part.key, "delivers")}>
                              {delivers}
                              {held.length > 0 && <span className="sr-only">. Move {held.length === 1 ? "it" : "them"} to another component before removing it.</span>}
                            </span>
                          </span>
                        </button>
                        <Button size="icon" variant="ghost" aria-label={`Remove component ${number}`}
                          blockedBy={held.length > 0 ? partId(part.key, "delivers") : undefined}
                          icon={<Trash2 size={16} aria-hidden="true" />} onClick={() => removeComponent(index)} />
                      </div>
                      {part.open && (
                        <div id={panelId} className="border-line grid gap-4 border-0 border-t border-solid p-4">
                          <div className="grid gap-4 sm:grid-cols-2">
                            <Input id={partId(part.key, "name")} required
                              label={<><span className="sr-only">Component {number} </span>Name</>}
                              value={part.name} error={problems.name} autoComplete="off"
                              onChange={(event) => {
                                updateComponent(part.key, { name: event.target.value });
                                clearComponentError(part.key, "name");
                                if (part.fresh && !part.idTouched) clearComponentError(part.key, "id");
                              }} />
                            <Input id={partId(part.key, "id")} required
                              label={<><span className="sr-only">Component {number} </span>ID</>}
                              className="font-mono" value={part.id} error={problems.id} autoComplete="off"
                              hint={part.fresh && !part.idTouched ? "Filled in from the name." : undefined}
                              onChange={(event) => {
                                updateComponent(part.key, { id: event.target.value, idTouched: true });
                                clearComponentError(part.key, "id");
                              }} />
                            <Input label={<><span className="sr-only">Component {number} </span>Arabic name</>} dir="auto"
                              value={part.name_ar} autoComplete="off"
                              onChange={(event) => updateComponent(part.key, { name_ar: event.target.value })} />
                            <Input label={<><span className="sr-only">Component {number} </span>Technology</>}
                              value={part.technology} autoComplete="off" placeholder="Example: Microservice"
                              onChange={(event) => updateComponent(part.key, { technology: event.target.value })} />
                          </div>
                          <TagInput label={<><span className="sr-only">Component {number} </span>Other names</>}
                            values={part.aliases} draft={part.draft} dir="auto"
                            hint="Press Enter after each." placeholder="Example: CPQ"
                            onChange={(aliases) => updateComponent(part.key, { aliases })}
                            onDraftChange={(draft) => updateComponent(part.key, { draft })} />
                          <Textarea label={<><span className="sr-only">Component {number} </span>What it does</>}
                            rows={2} dir="auto" value={part.description}
                            onChange={(event) => updateComponent(part.key, { description: event.target.value })} />
                          <p className="text-meta text-ink-soft m-0">
                            {held.length === 0 ? "No capability names this component yet; pick it under Capabilities."
                              : `Delivers ${held.map((item) => `“${item}”`).join(", ")}.`}
                          </p>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
            <Button id={addComponentId} size="sm" className="w-fit" icon={<Plus size={14} aria-hidden="true" />}
              onClick={addComponent}>
              Add component
            </Button>
          </Section>

          <Section id={`${base}-capabilities`} title={`Capabilities (${capabilities.length})`}
            description={<>
              What the system does, the business domain each belongs to, and the words in a requirement that point to it.
              {unplaced > 0 && !noDomains && ` ${plural(unplaced, "capability has", "capabilities have")} no domain yet.`}
            </>}>
            {capabilities.length === 0 ? (
              <p className="text-body text-ink-muted m-0">No capabilities yet. Add what this system does.</p>
            ) : (
              <ul role="list" className="m-0 grid list-none gap-2 p-0">
                {capabilities.map((capability, index) => {
                  const number = index + 1;
                  const panelId = fieldId(capability.key, "panel");
                  const problems = errors[capability.key] ?? {};
                  const domain = domainLabel(domains, capability.domain_id);
                  const part = components.find((item) => item.key === capability.component);
                  const partName = part ? part.name.trim() || "New component" : null;
                  const phrases = withDraft(capability.triggers, capability.draft).length;
                  const title = capability.name.trim() || "New capability";
                  const code = capability.id.trim();
                  const phraseCount = plural(phrases, "matching phrase", "matching phrases");
                  return (
                    <li key={capability.key}
                      className={cx("bg-surface rounded-md border border-solid",
                        Object.values(problems).some(Boolean) ? "border-danger" : "border-line")}>
                      <div className="flex items-start gap-2 p-2">
                        <button type="button" id={fieldId(capability.key, "toggle")}
                          aria-expanded={capability.open} aria-controls={panelId}
                          aria-label={`Capability ${number}: ${title}${code ? `, ID ${code}` : ""}, ${domain ?? "no domain"}${partName ? `, in ${partName}` : ""}, ${phraseCount}`}
                          className="grid min-h-11 min-w-0 flex-1 cursor-pointer gap-1 rounded-sm border-0 bg-transparent px-2 py-1.5 text-left hover:[background-color:color-mix(in_srgb,var(--accent)_6%,var(--surface))]"
                          onClick={() => update(capability.key, { open: !capability.open })}>
                          <span className="flex min-w-0 items-center gap-2">
                            <ChevronRight size={16} aria-hidden="true"
                              className={cx("text-ink-muted shrink-0 transition-transform duration-[var(--motion-fast)] motion-reduce:transition-none",
                                capability.open && "rotate-90")} />
                            <span className="text-body text-ink truncate font-semibold">{title}</span>
                            {code && <code className="text-meta text-ink-muted hidden truncate font-mono sm:inline">{code}</code>}
                          </span>
                          <span className="flex flex-wrap items-center gap-x-2 gap-y-1 pl-6">
                            {code && <code className="text-meta text-ink-muted font-mono sm:hidden">{code}</code>}
                            {domain ? (
                              <Badge icon={<Layers size={12} aria-hidden="true" />}>{domain}</Badge>
                            ) : (
                              <Badge tone="warning">No domain</Badge>
                            )}
                            {partName && <Badge icon={<Boxes size={12} aria-hidden="true" />}>{partName}</Badge>}
                            <span className="text-meta text-ink-muted">{phraseCount}</span>
                          </span>
                        </button>
                        <Button size="icon" variant="ghost" aria-label={`Remove capability ${number}`}
                          icon={<Trash2 size={16} aria-hidden="true" />} onClick={() => removeCapability(index)} />
                      </div>
                      {capability.open && (
                        <div id={panelId} className="border-line grid gap-4 border-0 border-t border-solid p-4">
                          <div className="grid gap-4 sm:grid-cols-2">
                            <Input id={fieldId(capability.key, "name")} required
                              label={<><span className="sr-only">Capability {number} </span>Name</>}
                              value={capability.name} error={problems.name} autoComplete="off"
                              onChange={(event) => {
                                update(capability.key, { name: event.target.value });
                                clearError(capability.key, "name");
                                if (capability.fresh && !capability.idTouched) clearError(capability.key, "id");
                              }} />
                            <Input id={fieldId(capability.key, "id")} required
                              label={<><span className="sr-only">Capability {number} </span>ID</>}
                              className="font-mono" value={capability.id} error={problems.id} autoComplete="off"
                              hint={capability.fresh
                                ? capability.idTouched ? undefined : "Filled in from the name."
                                : "Changing it replaces the capability in this version."}
                              onChange={(event) => {
                                update(capability.key, { id: event.target.value, idTouched: true });
                                clearError(capability.key, "id");
                              }} />
                          </div>
                          <Select label={<><span className="sr-only">Capability {number} </span>Domain</>}
                            value={capability.domain_id} disabled={noDomains}
                            hint={noDomains
                              ? "This version has no domains yet. Save, then add them under Capability domains below the systems list."
                              : "The business area this capability belongs to."}
                            onChange={(event) => update(capability.key, { domain_id: event.target.value })}>
                            <option value="">Not placed yet</option>
                            {tree.map(({ domain: item, depth }) => (
                              <option key={item.id} value={item.id}>{INDENT.repeat(depth)}{item.name}</option>
                            ))}
                          </Select>
                          <Select label={<><span className="sr-only">Capability {number} </span>Component</>}
                            value={capability.component === null ? "" : String(capability.component)}
                            disabled={components.length === 0}
                            hint={components.length === 0
                              ? "This system has no components. Add one under Components to place it."
                              : "The part of this system that delivers it."}
                            onChange={(event) => update(capability.key,
                              { component: event.target.value === "" ? null : Number(event.target.value) })}>
                            <option value="">Not in a component</option>
                            {components.map((item, position) => (
                              <option key={item.key} value={String(item.key)}>
                                {item.name.trim() || `Component ${position + 1}`}
                              </option>
                            ))}
                          </Select>
                          <TagInput id={fieldId(capability.key, "triggers")}
                            label={<><span className="sr-only">Capability {number} </span>Matching phrases</>}
                            required values={capability.triggers} draft={capability.draft} error={problems.triggers}
                            hint="Words a requirement might use when it touches this capability. Press Enter after each."
                            placeholder="Example: web ordering" dir="auto"
                            onChange={(triggers) => { update(capability.key, { triggers }); clearError(capability.key, "triggers"); }}
                            onDraftChange={(draft) => { update(capability.key, { draft }); clearError(capability.key, "triggers"); }} />
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
            <Button id={addCapabilityId} size="sm" className="w-fit" icon={<Plus size={14} aria-hidden="true" />}
              onClick={addCapability}>
              Add capability
            </Button>
          </Section>

          <Section id={`${base}-constraints`} title={`Known constraints (${filledConstraints})`}
            description="Limits a requirement touching this system must respect, one per row.">
            {constraints.length === 0 ? (
              <p className="text-body text-ink-muted m-0 max-w-[64ch]">
                No known constraints. Add one for each limit, for example “Read-only during the billing run”.
              </p>
            ) : (
              <ol className="m-0 grid list-none gap-2 p-0">
                {constraints.map((row, index) => (
                  <li key={row.key} className="flex items-center gap-2">
                    <span aria-hidden="true" className="text-meta text-ink-muted w-5 shrink-0 text-right tabular-nums">
                      {index + 1}
                    </span>
                    <Input id={constraintId(row.key)} fieldClassName="min-w-0 flex-1" dir="auto" value={row.text}
                      label={<span className="sr-only">Constraint {index + 1}</span>} autoComplete="off"
                      onChange={(event) => setConstraints((current) =>
                        current.map((item) => (item.key === row.key ? { ...item, text: event.target.value } : item)))}
                      onKeyDown={(event) => {
                        // Enter starts the next constraint rather than submitting the form,
                        // and only once this one has something in it.
                        if (event.key !== "Enter") return;
                        event.preventDefault();
                        if (row.text.trim()) addConstraint();
                      }} />
                    <Button size="icon" variant="ghost" className="min-h-9 min-w-9" aria-label={`Remove constraint ${index + 1}`}
                      icon={<Trash2 size={16} aria-hidden="true" />} onClick={() => removeConstraint(index)} />
                  </li>
                ))}
              </ol>
            )}
            <Button id={addConstraintId} size="sm" className="w-fit" icon={<Plus size={14} aria-hidden="true" />}
              onClick={addConstraint}>
              Add constraint
            </Button>
          </Section>
        </div>

        <div className="bg-surface-raised border-line sticky -bottom-6 z-[var(--z-sticky)] -mx-6 -mb-6 border-0 border-t border-solid px-6 pb-6">
          {error && <ErrorNotice message={error} />}
          <ModalFooter className="mt-4">
            <p className="text-meta text-ink-muted m-0 mr-auto">Saves to this version in progress, not the published catalogue.</p>
            <Button onClick={requestClose}>Cancel</Button>
            <Button type="submit" variant="primary" loading={saving} loadingLabel="Saving…">Save system</Button>
          </ModalFooter>
        </div>
      </form>
      {confirmingDiscard && (
        <ConfirmDialog
          title={creating ? "Discard this new system?" : `Discard changes to ${initial.name}?`}
          message="What you changed in this drawer has not been saved and will be lost."
          confirmLabel="Discard changes"
          onCancel={() => setConfirmingDiscard(false)}
          onConfirm={onCancel}
        />
      )}
    </Modal>
  );
}
