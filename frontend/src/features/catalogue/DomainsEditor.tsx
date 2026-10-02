import { useMutation } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { errorMessage } from "../../api/errors";
import { knowledgeApi, type CapabilityDomain, type KnowledgeRelease } from "../../api/knowledge";
import { ErrorNotice } from "../../components/ErrorNotice";
import {
  Button, Input, Modal, ModalBody, ModalFooter, ModalHeader, Select, Textarea, cx,
} from "../../components/ui";
import { domainLabel, domainTree, slug } from "./labels";

const INDENT = ["", "pl-6", "pl-12"] as const;
const EMPTY: CapabilityDomain = { id: "", name: "", name_ar: null, parent_id: null, description: null };

/** Which tree is edited: business areas capabilities belong to, or where systems sit (ADR-0094). */
export type DomainKind = "capability" | "landscape";

const COPY = {
  capability: {
    title: "Capability domains",
    intro: "Business areas that group what systems do. Place each capability in one when you edit its system.",
    add: "Add domain",
    adding: "Add a capability domain",
    nameHint: "A business area, such as Order capture.",
    parentHint: "Domains go up to three levels deep.",
    saved: "Domains saved.",
    empty: "No capability domains yet.",
    held: ["capability", "capabilities"],
  },
  landscape: {
    title: "Landscape domains",
    intro: "Where systems sit in the architecture landscape, such as Customer, with sub-domains such as Assisted. Place each system in one when you edit it.",
    add: "Add landscape domain",
    adding: "Add a landscape domain",
    nameHint: "An area of the landscape, such as Customer or Resource.",
    parentHint: "Choose a parent to make this a sub-domain, such as Assisted under Customer. Up to three levels deep.",
    saved: "Landscape domains saved.",
    empty: "No landscape domains yet.",
    held: ["system", "systems"],
  },
} as const;

function DomainDialog({ kind, initial, domains, creating, saving, error, onSave, onCancel }: {
  kind: DomainKind;
  initial: CapabilityDomain;
  domains: CapabilityDomain[];
  creating: boolean;
  saving: boolean;
  error: string | null;
  onSave: (domain: CapabilityDomain) => void;
  onCancel: () => void;
}) {
  const copy = COPY[kind];
  const titleId = useId();
  const [name, setName] = useState(initial.name);
  const [nameAr, setNameAr] = useState(initial.name_ar ?? "");
  const [parent, setParent] = useState(initial.parent_id ?? "");
  const [description, setDescription] = useState(initial.description ?? "");
  // A domain cannot sit inside itself or anything inside it, nor below the third level.
  const inside = new Set<string>([initial.id]);
  for (const { domain } of domainTree(domains)) {
    if (domain.parent_id && inside.has(domain.parent_id)) inside.add(domain.id);
  }
  const parents = domainTree(domains).filter(({ domain, depth }) => depth < 2 && !inside.has(domain.id));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const taken = new Set(domains.map((item) => item.id));
    let id = initial.id;
    if (creating) {
      // A landscape sub-domain's key says where it sits: "customer-assisted".
      const base = slug(kind === "landscape" && parent ? `${parent} ${name}` : name, "domain");
      id = base;
      for (let suffix = 2; taken.has(id); suffix += 1) id = `${base}-${suffix}`;
    }
    onSave({
      id, name: name.trim(), name_ar: nameAr.trim() || null,
      parent_id: parent || null, description: description.trim() || null,
    });
  };

  return (
    <Modal variant="drawer" side="right" size="md" labelledBy={titleId} onClose={onCancel}>
      <form onSubmit={submit} className="grid gap-4">
        <ModalHeader id={titleId} title={creating ? copy.adding : `Edit ${initial.name}`} />
        <ModalBody>
          <Input label="Name" hint={copy.nameHint} required value={name}
            onChange={(event) => setName(event.target.value)} />
          <Input label="Arabic name" dir="auto" value={nameAr} onChange={(event) => setNameAr(event.target.value)} />
          <Select label="Parent domain" hint={copy.parentHint} value={parent}
            onChange={(event) => setParent(event.target.value)}>
            <option value="">None: a top-level domain</option>
            {parents.map(({ domain }) => (
              <option key={domain.id} value={domain.id}>{domainLabel(domains, domain.id)}</option>
            ))}
          </Select>
          <Textarea label="Description" rows={3} dir="auto" value={description}
            onChange={(event) => setDescription(event.target.value)} />
          {error && <ErrorNotice message={error} />}
        </ModalBody>
        <ModalFooter>
          <Button onClick={onCancel}>Cancel</Button>
          <Button type="submit" variant="primary" loading={saving} loadingLabel="Saving…">Save domain</Button>
        </ModalFooter>
      </form>
    </Modal>
  );
}

/**
 * One of the version's two domain trees. Capability domains (ADR-0089) are
 * business areas that group what systems do; landscape domains (ADR-0094) are
 * where the systems themselves sit. A domain still holding something, or other
 * domains, cannot be removed, and says what it holds instead.
 */
export function DomainsEditor({ draft, onChanged, kind = "capability" }: {
  draft: KnowledgeRelease;
  onChanged: () => void;
  kind?: DomainKind;
}) {
  const copy = COPY[kind];
  // The systems editor jumps to "domains-title" when a version has no capability domains.
  const titleId = kind === "landscape" ? "landscape-domains-title" : "domains-title";
  const domains = (kind === "landscape" ? draft.landscape_domains : draft.capability_domains) ?? [];
  const [editing, setEditing] = useState<{ domain: CapabilityDomain; creating: boolean } | null>(null);
  const [status, setStatus] = useState("");
  const save = useMutation({
    mutationFn: knowledgeApi.save,
    onSuccess: () => {
      setEditing(null);
      setStatus(copy.saved);
      onChanged();
    },
  });
  // What each domain holds, and which systems that is, so a domain that cannot
  // be removed says what to move first.
  const holdings = new Map<string, { count: number; systems: Set<string> }>();
  const hold = (domainId: string | null | undefined, system: string) => {
    if (!domainId) return;
    const held = holdings.get(domainId) ?? { count: 0, systems: new Set<string>() };
    held.count += 1;
    held.systems.add(system);
    holdings.set(domainId, held);
  };
  for (const system of draft.systems) {
    if (kind === "landscape") hold(system.landscape_domain_id, system.name);
    else for (const capability of system.capabilities) hold(capability.domain_id, system.name);
  }
  const unplaced = kind === "landscape"
    ? draft.systems.filter((system) => !system.landscape_domain_id).length
    : draft.systems.reduce(
      (count, system) => count + system.capabilities.filter((item) => !item.domain_id).length, 0);
  const [one, many] = copy.held;
  const saveDomains = (next: CapabilityDomain[]) => save.mutate(kind === "landscape"
    ? { ...draft, landscape_domains: next }
    : { ...draft, capability_domains: next });

  return (
    <section className="grid min-w-0 gap-3" aria-labelledby={titleId}>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid gap-1">
          <h4 className="text-body text-ink m-0 font-semibold" id={titleId} tabIndex={-1}>
            {copy.title} ({domains.length})
          </h4>
          <p className="text-meta text-ink-muted m-0 max-w-[68ch]">
            {copy.intro}
            {unplaced > 0 && ` ${unplaced === 1 ? `1 ${one} is` : `${unplaced} ${many} are`} not placed yet.`}
          </p>
        </div>
        <Button icon={<Plus size={16} aria-hidden="true" />}
          onClick={() => { save.reset(); setEditing({ domain: EMPTY, creating: true }); }}>
          {copy.add}
        </Button>
      </header>
      {save.error && !editing && <ErrorNotice message={errorMessage(save.error)} />}
      {status && <p className="text-meta text-ink-soft m-0" role="status">{status}</p>}
      {domains.length === 0 ? (
        <p className="text-body text-ink-muted m-0">{copy.empty}</p>
      ) : (
        <ul role="list" className="border-line m-0 grid list-none rounded-md border border-solid p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">
          {domainTree(domains).map(({ domain, depth }) => {
            const held = holdings.get(domain.id);
            const inner = domains.filter((item) => item.parent_id === domain.id).length;
            const holds = [
              held && (kind === "landscape"
                ? `${held.count === 1 ? one : many} ${[...held.systems].sort().join(", ")}`
                : `${held.count} ${held.count === 1 ? one : many} from ${[...held.systems].sort().join(", ")}`),
              inner > 0 && `${inner} ${inner === 1 ? "domain" : "domains"} inside`,
            ].filter(Boolean).join("; ");
            const reasonId = `${kind}-domain-${domain.id}-holds`;
            return (
              <li key={domain.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                <span className={cx("grid min-w-0 flex-1 gap-0.5", INDENT[Math.min(depth, 2)])}>
                  <span className="text-body text-ink">
                    {domain.name}
                    {domain.name_ar && <span className="text-meta text-ink-muted" dir="auto"> · {domain.name_ar}</span>}
                  </span>
                  <span className="text-meta text-ink-muted" id={reasonId}>
                    {holds ? `Holds ${holds}. Move them to remove this domain.` : "Empty"}
                  </span>
                </span>
                <span className="flex flex-wrap gap-1">
                  <Button size="sm" variant="ghost" icon={<Pencil size={14} aria-hidden="true" />}
                    aria-label={`Edit ${domain.name}`}
                    onClick={() => { save.reset(); setEditing({ domain, creating: false }); }}>
                    Edit
                  </Button>
                  <Button size="sm" variant="ghost" icon={<Trash2 size={14} aria-hidden="true" />}
                    disabled={save.isPending} blockedBy={holds ? reasonId : undefined}
                    aria-label={`Remove ${domain.name}`}
                    onClick={() => saveDomains(domains.filter((item) => item.id !== domain.id))}>
                    Remove
                  </Button>
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {editing && (
        <DomainDialog
          kind={kind}
          initial={editing.domain}
          domains={domains}
          creating={editing.creating}
          saving={save.isPending}
          error={save.error ? errorMessage(save.error) : null}
          onSave={(domain) => saveDomains(editing.creating
            ? [...domains, domain]
            : domains.map((item) => (item.id === domain.id ? domain : item)))}
          onCancel={() => setEditing(null)}
        />
      )}
    </section>
  );
}
