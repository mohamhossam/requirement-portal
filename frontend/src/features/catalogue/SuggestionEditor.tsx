import { useId, useState, type FormEvent } from "react";

import type { Component, ProductOffering, RelationshipKind, Suggestion, SuggestionContent } from "../../api/knowledge";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Button, Input, Modal, ModalBody, ModalFooter, ModalHeader, Select, Textarea } from "../../components/ui";
import { RELATIONSHIP_KINDS, RELATIONSHIP_KIND_LABEL } from "./labels";
import { JourneyDrawer } from "./JourneyDrawer";
import { ProductDrawer } from "./ProductDrawer";

const TITLE: Record<SuggestionContent["kind"], string> = {
  system: "Edit the system before accepting",
  component: "Edit the component before accepting",
  capability: "Edit the capability before accepting",
  constraint: "Edit the constraint before accepting",
  relationship: "Edit the dependency before accepting",
  landscape_domain: "Edit the landscape domain before accepting",
  placement: "Edit where the system sits before accepting",
  product: "Edit the product offering before accepting",
  journey: "Edit the journey before accepting",
};

const list = (value: string) => value.split(/[\n,;]/).map((item) => item.trim()).filter(Boolean);

/** Correct what the AI read, then accept it; the kind of item never changes. */
export function SuggestionEditor({
  suggestion,
  systems,
  domains = [],
  offerings = [],
  saving,
  error,
  onSave,
  onCancel,
}: {
  suggestion: Suggestion;
  systems: { id: string; name: string; components: Component[] }[];
  /** Landscape domains by path, from the draft and from suggestions still waiting. */
  domains?: { id: string; label: string }[];
  /** Product offerings, from the draft and from suggestions still waiting. */
  offerings?: ProductOffering[];
  saving: boolean;
  error: string | null;
  onSave: (content: SuggestionContent) => void;
  onCancel: () => void;
}) {
  const titleId = useId();
  const original = suggestion.content;
  const [content, setContent] = useState<SuggestionContent>(original);
  const [aliases, setAliases] = useState(original.aliases.join(", "));
  const [triggers, setTriggers] = useState(original.triggers.join(", "));
  const set = (changes: Partial<SuggestionContent>) => setContent((current) => ({ ...current, ...changes }));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSave({ ...content, aliases: list(aliases), triggers: list(triggers) });
  };
  const parts = systems.find((system) => system.id === content.system_id)?.components ?? [];
  if (original.kind === "product" && original.product) {
    // An offering is corrected in the same drawer that edits one by hand.
    return (
      <ProductDrawer initial={original.product} systems={systems} taken={[]} creating={false}
        saving={saving} error={error} title={TITLE.product} saveLabel="Accept with these edits"
        onSave={(offering) => onSave({ ...original, system_id: offering.id, name: offering.name, product: offering })}
        onCancel={onCancel} />
    );
  }
  if (original.kind === "journey" && original.journey) {
    // A journey is corrected in the same drawer that edits one by hand.
    return (
      <JourneyDrawer initial={original.journey} systems={systems} offerings={offerings} taken={[]} creating={false}
        saving={saving} error={error} title={TITLE.journey} saveLabel="Accept with these edits"
        onSave={(journey) => onSave({ ...original, system_id: journey.id, name: journey.name, journey })}
        onCancel={onCancel} />
    );
  }
  const domainSelect = (label: string, value: string, none: string | null, onChange: (value: string) => void,
    hint?: string) => (
    <Select label={label} hint={hint} value={value} onChange={(event) => onChange(event.target.value)}>
      {none !== null && <option value="">{none}</option>}
      {value && !domains.some((domain) => domain.id === value) && <option value={value}>{value}</option>}
      {domains.filter((domain) => domain.id !== content.landscape_domain_id || original.kind !== "landscape_domain")
        .map((domain) => <option key={domain.id} value={domain.id}>{domain.label}</option>)}
    </Select>
  );
  const systemSelect = (label: string, value: string, onChange: (value: string) => void) => (
    <Select label={label} value={value} onChange={(event) => onChange(event.target.value)}>
      {!systems.some((system) => system.id === value) && <option value={value}>{value}</option>}
      {systems.map((system) => <option key={system.id} value={system.id}>{system.name}</option>)}
    </Select>
  );

  return (
    <Modal variant="dialog" labelledBy={titleId} onClose={onCancel}>
      <form onSubmit={submit}>
        <ModalHeader id={titleId} title={TITLE[original.kind]}
          description={`Source: “${suggestion.citations[0]?.quote ?? ""}”`} />
        <ModalBody>
          {original.kind === "system" && <>
            <Input label="System ID" hint="A short, stable key such as bcrm." required value={content.system_id}
              onChange={(event) => set({ system_id: event.target.value })} />
            <Input label="Name" required value={content.name} onChange={(event) => set({ name: event.target.value })} />
            <Input label="Arabic name" dir="auto" value={content.name_ar ?? ""}
              onChange={(event) => set({ name_ar: event.target.value || null })} />
            <Input label="Other names" hint="Separate names with commas." value={aliases}
              onChange={(event) => setAliases(event.target.value)} />
            <Textarea label="Description" hint="What the system is for." rows={2} dir="auto"
              value={content.description ?? ""} onChange={(event) => set({ description: event.target.value || null })} />
          </>}
          {original.kind === "landscape_domain" && <>
            <Input label="Name" required value={content.name} onChange={(event) => set({ name: event.target.value })} />
            <Input label="Arabic name" dir="auto" value={content.name_ar ?? ""}
              onChange={(event) => set({ name_ar: event.target.value || null })} />
            {domainSelect("Parent domain", content.parent_domain_id ?? "", "None: a top-level domain",
              (value) => set({ parent_domain_id: value || null }), "Choose a parent to make this a sub-domain.")}
            <Textarea label="Description" rows={2} dir="auto" value={content.description ?? ""}
              onChange={(event) => set({ description: event.target.value || null })} />
          </>}
          {original.kind === "placement" && <>
            {systemSelect("System", content.system_id, (value) => set({ system_id: value }))}
            {domainSelect("Landscape domain", content.landscape_domain_id ?? "", null,
              (value) => set({ landscape_domain_id: value }), "Where the system sits in the landscape.")}
          </>}
          {original.kind === "component" && <>
            {systemSelect("System", content.system_id, (value) => set({ system_id: value }))}
            <Input label="Component name" required value={content.name}
              onChange={(event) => set({ name: event.target.value })} />
            <Input label="Component ID" required value={content.component_id ?? ""}
              onChange={(event) => set({ component_id: event.target.value })} />
            <Input label="Arabic name" dir="auto" value={content.name_ar ?? ""}
              onChange={(event) => set({ name_ar: event.target.value || null })} />
            <Input label="Other names" hint="Separate names with commas." value={aliases}
              onChange={(event) => setAliases(event.target.value)} />
            <Input label="Technology" hint="What it is built as, such as Microservice." value={content.technology ?? ""}
              onChange={(event) => set({ technology: event.target.value || null })} />
            <Textarea label="What it does" rows={2} dir="auto" value={content.description ?? ""}
              onChange={(event) => set({ description: event.target.value || null })} />
          </>}
          {original.kind === "capability" && <>
            {systemSelect("System", content.system_id, (value) => set({ system_id: value }))}
            <Input label="Capability name" required value={content.name}
              onChange={(event) => set({ name: event.target.value })} />
            <Input label="Capability ID" required value={content.capability_id ?? ""}
              onChange={(event) => set({ capability_id: event.target.value })} />
            <Input label="Matching phrases" hint="Words a requirement might use. Separate them with commas." required
              value={triggers} onChange={(event) => setTriggers(event.target.value)} />
            <Select label="Component" hint="The part of the system that delivers it."
              value={content.component_id ?? ""} onChange={(event) => set({ component_id: event.target.value || null })}>
              <option value="">Not in a component</option>
              {content.component_id && !parts.some((part) => part.id === content.component_id) && (
                <option value={content.component_id}>{content.component_id} (suggested, not in this version yet)</option>
              )}
              {parts.map((part) => <option key={part.id} value={part.id}>{part.name}</option>)}
            </Select>
          </>}
          {original.kind === "constraint" && <>
            {systemSelect("System", content.system_id, (value) => set({ system_id: value }))}
            <Textarea label="Constraint" required rows={3} dir="auto" value={content.text}
              onChange={(event) => set({ text: event.target.value })} />
          </>}
          {original.kind === "relationship" && <>
            {systemSelect("Depends from", content.system_id, (value) => set({ system_id: value }))}
            {systemSelect("Depends on", content.target_system_id ?? "", (value) => set({ target_system_id: value }))}
            <Input label="What the dependency is for" required value={content.text}
              onChange={(event) => set({ text: event.target.value })} />
            <Select label="How it depends" value={content.relationship_kind ?? "unspecified"}
              hint="Leave it as Not stated unless the document says how."
              onChange={(event) => set({ relationship_kind: event.target.value as RelationshipKind })}>
              {RELATIONSHIP_KINDS.map((kind) => <option key={kind} value={kind}>{RELATIONSHIP_KIND_LABEL[kind]}</option>)}
            </Select>
          </>}
          {error && <ErrorNotice message={error} />}
        </ModalBody>
        <ModalFooter>
          <Button onClick={onCancel}>Cancel</Button>
          <Button type="submit" variant="primary" loading={saving} loadingLabel="Adding…">Accept with these edits</Button>
        </ModalFooter>
      </form>
    </Modal>
  );
}
