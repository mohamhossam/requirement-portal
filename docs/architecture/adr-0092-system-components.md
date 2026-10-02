# ADR 0092 — System components

## Status

Accepted. Extends ADR-0016, ADR-0067, ADR-0081 and ADR-0089.

## Context

A catalogue system was one flat list of capabilities. Real systems are made of parts: BCRM has an
agent desk and a quote engine, and each delivers its own capabilities. Maintainers had nowhere to
record this, so:
- **the dossier read one long list**, with no way to see which part of a system does what;
- **files could not carry the structure**, even when a source document stated it;
- **document reading dropped it.** A design document's "the Pricing service approves
  discounts" became a capability with no record of the service.

Two shapes were possible:
- **strict nesting** (System → Components → Capabilities, where capabilities exist only inside a
  component);
- **a reference** from each capability to a component of its own system.

Strict nesting would change the capability's address. That address is the diff key, the
suggestion lookup, the impact snapshot, the approval fingerprint and the evidence chunk. It would
also break every stored release and file.

## Decision

- **Components belong to one system, and capabilities point at them.**
  - `SystemComponent(id, name, name_ar, description, aliases, technology)` lives in
    `SystemDefinition.components`.
  - `KnowledgeCapability.component_id` is optional and must name a component of the same system.
    So a component that still delivers a capability cannot be removed.
  - Capabilities stay on the system, so ids, diff keys, the index and stored releases do not change.
- **Within a system,** component ids are unique, and a name, Arabic name or alias identifies one
  component.
- **Component names never select a system.**
  - They are not part of the system-alias ownership check, and not part of matching or evidence
    text.
  - Two systems may each have a component called "Portal".
  - `technology` is free text in the maintainer's words, not an enum.
- **No migration.**
  - Releases are stored as one JSONB document. Missing keys read as `components=()` and
    `component_id=None`.
  - The packaged seed is unchanged. The project records no component structure for the SMB
    landscape, and inventing one would be an invented business rule (AGENTS §10).
- **Files.**
  - YAML and JSON take an optional `components` list per system and a `component` key per
    capability, matching the existing `domain` key.
  - Excel has an optional Components sheet (`system_id, component_id, name, name_ar, aliases,
    technology, description`) and an optional `component_id` column on Capabilities.
  - Older files import unchanged. A capability placed in an unknown component is refused, with
    its location named.
- **Diff.**
  - `ChangedItem.COMPONENT` is keyed `system/component`, with field changes `name`, `name_ar`,
    `aliases`, `description` and `technology`.
  - A capability reports a `component` field change.
- **Document reading proposes components.** The prompt moves to `catalogue-extraction-v4`.
  - A `component` suggestion carries `component_id`, `name`, `name_ar`, `aliases`, `description`
    and `technology`. The model's `text` field is the component's description, and `technology`
    is a new output field.
  - A capability suggestion may name its component (`component`, slugged into `component_id`).
  - The known-systems payload lists each system's component names, so the model reuses them.
  - A capability naming a component its system lacks is `needs_component`, mirroring
    `needs_system`.
  - Accepting a component adds it, or fills in an existing one's empty fields and its free
    labels.
  - A capability suggestion places a capability that has no component. It never moves one, which
    is the same rule ADR-0089 set for domains.
  - Accept-all order is system → component → capability → constraint → relationship. A
    capability whose component is still missing waits for a one-by-one decision.
- **Impacts are show-only.**
  - `SystemCapability` gains `component_id` and `component_name`, taken from the pinned release
    at mapping time.
  - Fingerprints, review-evidence digests and generation prompts ignore them, so existing
    approvals stay valid and the `feature-v5` and `story-v5` prompts are unchanged.
  - Payloads write them only when present.
- **Export.**
  - The neutral contract moves to `1.4`: `ExportCapability.component`.
  - The Systems sheet gains a `capability_components` column.
- **UI.**
  - The system dialog gets a Components section (ID, name, Arabic name, technology, other names,
    what it does) and a component picker per capability.
  - A component that still delivers capabilities explains why it cannot be removed.
  - The dossier groups "What it does" by component, with "Not in a component" last.
  - Suggestions review and edit components.
  - The impact panel names each matched capability's component.

## Consequences

- Maintainers can record how a system is built and read the dossier part by part. Documents that
  describe services and modules feed that structure through review.
- **Components are organisational only.**
  - A requirement that names a component ("the quote engine") still maps through the system's
    names and capability phrases.
  - Making component names evidence would change retrieval, mapped content and fingerprints. It
    is left as a follow-up that needs its own decision.
- One more structure to curate. Capabilities not in a component stay visible under "Not in a
  component".
- A component cannot be shared by two systems. A shared platform stays a system with dependencies.

## Alternatives Considered

- **Strict nesting (System → Components → Capabilities).** Rejected: it breaks capability
  addressing everywhere (diff, suggestions, impacts, fingerprints, files, stored releases) for no
  gain the reference does not give.
- **Components as catalogue-level entities shared across systems.** Rejected: dependencies between
  systems already model shared platforms, and a shared component would need its own ownership and
  matching rules.
- **Component names as matching evidence now.** Rejected for this slice: it changes which systems
  map and invalidates approvals. The product owner chose show-only.
- **A fixed technology enum.** Rejected: the organisation has not defined one, and inventing it
  would be a business rule.
