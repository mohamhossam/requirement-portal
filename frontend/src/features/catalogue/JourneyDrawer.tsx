import { ChevronRight, Lock, Plus, Trash2, X } from "lucide-react";
import { useId, useRef, useState, type FormEvent, type ReactNode } from "react";

import type {
  Activity, ActivityIntegration, FlowRule, FlowRuleKind, Journey, ProductOffering, SourceConfidence,
} from "../../api/knowledge";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Button, Checkbox, Input, Modal, ModalFooter, ModalHeader, Select, Textarea, cx } from "../../components/ui";
import { CONFIDENCES, CONFIDENCE_LABEL, RULE_KINDS, RULE_LABEL, slug } from "./labels";

type StepRow = {
  key: number; original: Activity | null; open: boolean; number: string; name: string; phase: string; track: string;
  performing: string; supporting: string[]; system_function: string; mode: string; customer_visible: string;
  description: string; components: string[]; input: string; output: string; etom: string;
  confidence: SourceConfidence | "";
};
type RuleRow = {
  key: number; original: FlowRule | null; kind: FlowRuleKind; from: string; to: string; condition: string;
  branch: string; parallel_group: string; rejoin_at: string;
};
type LinkRow = {
  key: number; original: ActivityIntegration | null; from: string; to: string; interaction: string;
  interface: string; payload: string; timing: string; correlation_key: string;
};
type Errors = Record<string, string>;

const text = (value: string) => value.trim() || null;
const flag = (value: boolean | null | undefined) => (value == null ? "" : value ? "yes" : "no");

function Section({ id, title, description, children }: {
  id: string; title: ReactNode; description?: ReactNode; children: ReactNode;
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
 * Add or edit one journey in a version in progress (ADR-0096).
 *
 * Four parts: the journey and the offering and order type it fulfils, its
 * activities in order, the rules for exceptions and side tracks, and how each
 * activity hands over to the next. The flow itself is never drawn here: it is
 * derived from the activities and rules, so a person edits those, not arrows.
 * Activities fold to one line each, so an 18-step journey is still one screen.
 */
export function JourneyDrawer({
  initial, systems: knownSystems, offerings: knownOfferings, taken, creating, saving, error, onSave, onCancel, title,
  saveLabel = "Save journey",
}: {
  initial: Journey;
  systems: { id: string; name: string }[];
  offerings: ProductOffering[];
  /** Journey ids already used, so a new one gets its own. */
  taken: string[];
  creating: boolean;
  saving: boolean;
  error: string | null;
  onSave: (journey: Journey) => void;
  onCancel: () => void;
  /** In place of "Edit <name>", when the drawer corrects a suggestion before it is accepted. */
  title?: string;
  saveLabel?: string;
}) {
  const base = useId();
  // A suggestion may name a system or offering this version does not have yet: it stays
  // chosen, marked so, rather than being dropped by a correction.
  const absent = (id: string) => `${id} (not in this version)`;
  const named = new Set(knownSystems.map((system) => system.id));
  const systems = [...knownSystems, ...[...new Set((initial.activities ?? [])
    .flatMap((item) => [item.performing_system_id ?? "", ...(item.supporting_system_ids ?? [])]))]
    .filter((id) => id && !named.has(id)).map((id) => ({ id, name: absent(id) }))];
  const missingOffering = initial.product_id && !knownOfferings.some((item) => item.id === initial.product_id)
    ? initial.product_id : null;
  const offerings: ProductOffering[] = missingOffering
    ? [...knownOfferings, { id: missingOffering, name: absent(missingOffering), order_types: [], components: [],
      values: [], audiences: [], rules: [] }]
    : knownOfferings;
  const titleId = `${base}-title`;
  // Rows that arrive are keyed by position; rows added here count on from far above.
  const counter = useRef(1_000_000);
  const next = () => (counter.current += 1);

  const [name, setName] = useState(initial.name);
  const [id, setId] = useState(initial.id);
  const [idTouched, setIdTouched] = useState(!creating);
  const [product, setProduct] = useState(initial.product_id ?? "");
  const [order, setOrder] = useState(initial.order_type_code ?? "");
  const [description, setDescription] = useState(initial.description ?? "");
  const [confidence, setConfidence] = useState<SourceConfidence | "">(initial.confidence ?? "");
  const [source, setSource] = useState(initial.source ?? "");
  const [steps, setSteps] = useState<StepRow[]>(() => (initial.activities ?? []).map((item, index) => ({
    key: index, original: item, open: false, number: item.number, name: item.name, phase: item.phase ?? "",
    track: item.track ?? "", performing: item.performing_system_id ?? "", supporting: item.supporting_system_ids ?? [],
    system_function: item.system_function ?? "", mode: item.mode ?? "", customer_visible: flag(item.customer_visible),
    description: item.description ?? "", components: item.component_ids ?? [], input: item.input ?? "",
    output: item.output ?? "", etom: item.etom ?? "", confidence: item.confidence ?? "",
  })));
  const [rules, setRules] = useState<RuleRow[]>(() => (initial.flow_rules ?? []).map((rule, index) => ({
    key: 10_000 + index, original: rule, kind: rule.kind, from: rule.from_activity, to: rule.to_activity,
    condition: rule.condition ?? "", branch: rule.branch ?? "", parallel_group: rule.parallel_group ?? "",
    rejoin_at: rule.rejoin_at ?? "",
  })));
  const [links, setLinks] = useState<LinkRow[]>(() => (initial.integrations ?? []).map((link, index) => ({
    key: 20_000 + index, original: link, from: link.from_activity, to: link.to_activity,
    interaction: link.interaction ?? "", interface: link.interface ?? "", payload: link.payload ?? "",
    timing: link.timing ?? "", correlation_key: link.correlation_key ?? "",
  })));
  const [errors, setErrors] = useState<Errors>({});
  const [confirmingDiscard, setConfirmingDiscard] = useState(false);

  const offering = offerings.find((item) => item.id === product);
  const names = new Map(systems.map((system) => [system.id, system.name]));
  const numbers = steps.map((step) => step.number.trim()).filter(Boolean);
  const updateStep = (key: number, changes: Partial<StepRow>) =>
    setSteps((current) => current.map((step) => (step.key === key ? { ...step, ...changes } : step)));
  const updateRule = (key: number, changes: Partial<RuleRow>) =>
    setRules((current) => current.map((rule) => (rule.key === key ? { ...rule, ...changes } : rule)));
  const updateLink = (key: number, changes: Partial<LinkRow>) =>
    setLinks((current) => current.map((link) => (link.key === key ? { ...link, ...changes } : link)));

  const journey = (): Journey => ({
    ...initial,
    id: id.trim(), name: name.trim(), product_id: product || null, order_type_code: product ? order || null : null,
    description: text(description), confidence: confidence || null, source: text(source),
    activities: steps.map((step) => ({
      ...(step.original ?? {}), number: step.number.trim(), name: step.name.trim(), phase: text(step.phase),
      track: text(step.track), performing_system_id: step.performing || null, supporting_system_ids: step.supporting,
      system_function: text(step.system_function), mode: text(step.mode),
      customer_visible: step.customer_visible === "" ? null : step.customer_visible === "yes",
      description: text(step.description),
      // Components belong to the offering: another offering's are dropped, an absent one's kept.
      component_ids: product && product === missingOffering ? step.components
        : step.components.filter((part) => (offering?.components ?? []).some((item) => item.id === part)),
      input: text(step.input), output: text(step.output), etom: text(step.etom), confidence: step.confidence || null,
    })),
    flow_rules: rules.map((rule) => ({
      ...(rule.original ?? {}), kind: rule.kind, from_activity: rule.from, to_activity: rule.to,
      condition: text(rule.condition), branch: text(rule.branch), parallel_group: text(rule.parallel_group),
      rejoin_at: rule.kind === "parallel" ? rule.rejoin_at || null : null,
    })),
    integrations: links.map((link) => ({
      ...(link.original ?? {}), from_activity: link.from, to_activity: link.to, interaction: text(link.interaction),
      interface: text(link.interface), payload: text(link.payload), timing: text(link.timing),
      correlation_key: text(link.correlation_key),
    })),
    // The flow is derived on the server from the activities and rules.
    edges: [],
  });
  const [baseline] = useState(() => JSON.stringify(journey()));
  const dirty = JSON.stringify(journey()) !== baseline;
  const requestClose = () => (dirty ? setConfirmingDiscard(true) : onCancel());

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    if (!name.trim()) found.name = "Give the journey a name.";
    if (creating && !id.trim()) found.id = "Give the journey an ID.";
    else if (creating && taken.includes(id.trim())) found.id = "Another journey has this ID.";
    const seen = new Set<string>();
    for (const step of steps) {
      const number = step.number.trim();
      if (!number) found[`step-${step.key}-number`] = "Give the activity a number.";
      else if (seen.has(number)) found[`step-${step.key}-number`] = "Another activity has this number.";
      seen.add(number);
      if (!step.name.trim()) found[`step-${step.key}-name`] = "Give the activity a name.";
    }
    for (const rule of rules) {
      if (!rule.from) found[`rule-${rule.key}-from`] = "Choose the activity it leaves.";
      if (!rule.to) found[`rule-${rule.key}-to`] = "Choose the activity it goes to.";
    }
    for (const link of links) {
      if (!link.from) found[`link-${link.key}-from`] = "Choose the activity it hands over from.";
      if (!link.to) found[`link-${link.key}-to`] = "Choose the activity it hands over to.";
    }
    setErrors(found);
    const first = Object.keys(found)[0];
    if (first) {
      // A folded activity hides its fields, so open the ones at fault.
      setSteps((current) => current.map((step) => (Object.keys(found).some((key) => key.startsWith(`step-${step.key}-`))
        ? { ...step, open: true } : step)));
      requestAnimationFrame(() => document.getElementById(`${base}-${first}`)?.focus());
      return;
    }
    onSave(journey());
  };
  const field = (key: string) => ({ id: `${base}-${key}`, error: errors[key] });
  const activitySelect = (label: ReactNode, value: string, key: string | null, onChange: (value: string) => void,
    none = "Choose an activity") => (
    <Select label={label} value={value} {...(key ? field(key) : {})} onChange={(event) => onChange(event.target.value)}>
      <option value="">{none}</option>
      {steps.filter((step) => step.number.trim()).map((step) => (
        <option key={step.key} value={step.number.trim()}>{step.number.trim()}. {step.name.trim() || "Unnamed"}</option>
      ))}
    </Select>
  );

  return (
    <Modal variant="drawer" side="right" size="lg" labelledBy={titleId} onClose={requestClose}
      closeOnOutsideClick={!dirty} className="[scroll-padding-top:8rem] [scroll-padding-bottom:6rem]">
      <form onSubmit={submit} noValidate className="grid min-h-full grid-rows-[auto_1fr_auto]">
        <div className="bg-surface-raised border-line sticky -top-6 z-[var(--z-sticky)] -mx-6 -mt-6 border-0 border-b border-solid px-6 pt-6">
          <div className="pr-10">
            <ModalHeader id={titleId} eyebrow={creating ? "New journey" : "Journey"}
              title={title ?? (creating ? "Add a journey" : `Edit ${initial.name}`)}
              description={<span className="text-meta">
                {`${steps.length} ${steps.length === 1 ? "activity" : "activities"} · ${rules.length} ${rules.length === 1 ? "rule" : "rules"} · ${links.length} ${links.length === 1 ? "integration" : "integrations"}`}
              </span>} />
          </div>
          <Button size="icon" variant="ghost" className="absolute top-5 right-5" aria-label="Close"
            icon={<X size={18} aria-hidden="true" />} onClick={requestClose} />
        </div>

        <div className="text-body text-ink-soft grid content-start gap-6 py-6 [&>section+section]:[border-top:1px_solid_var(--line)] [&>section+section]:pt-6">
          <Section id={`${base}-about`} title="The journey">
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Name" required value={name} autoComplete="off" {...field("name")}
                placeholder="Example: New Activation"
                onChange={(event) => {
                  setName(event.target.value);
                  if (creating && !idTouched) setId(slug(event.target.value, ""));
                }} />
              {creating ? (
                <Input label="Journey ID" required className="font-mono" value={id} autoComplete="off" {...field("id")}
                  hint="Filled in from the name. A short, stable key; it cannot change once saved."
                  onChange={(event) => { setId(event.target.value); setIdTouched(true); }} />
              ) : (
                <div className="grid gap-1">
                  <span className="text-label text-ink">Journey ID</span>
                  <p className="m-0 flex flex-wrap items-center gap-2">
                    <Lock className="text-ink-muted shrink-0" size={14} aria-hidden="true" />
                    <code className="text-body text-ink font-mono">{initial.id}</code>
                  </p>
                </div>
              )}
              <Select label="Product offering" value={product} hint="The offering whose order this journey fulfils."
                onChange={(event) => { setProduct(event.target.value); setOrder(""); }}>
                <option value="">Not tied to an offering</option>
                {offerings.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </Select>
              <Select label="Order type" value={order} disabled={!offering}
                hint={offering ? "Which of its order types this journey fulfils." : "Choose a product offering first."}
                onChange={(event) => setOrder(event.target.value)}>
                <option value="">Not stated</option>
                {(offering?.order_types ?? []).map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
              </Select>
              <Select label="Confidence" value={confidence} onChange={(event) => setConfidence(event.target.value as SourceConfidence | "")}>
                <option value="">Not stated</option>
                {CONFIDENCES.map((item) => <option key={item} value={item}>{CONFIDENCE_LABEL[item].label}</option>)}
              </Select>
              <Input label="Source" value={source} onChange={(event) => setSource(event.target.value)} />
            </div>
            <Textarea label="Description" rows={2} dir="auto" value={description}
              onChange={(event) => setDescription(event.target.value)} />
          </Section>

          <Section id={`${base}-activities`} title={`Activities (${steps.length})`}
            description="Numbered in the order they run. The main track runs top to bottom; give side tracks, such as a correction, a track name.">
            {steps.length === 0 && <p className="text-body text-ink-muted m-0">No activities yet.</p>}
            <ol className="m-0 grid list-none gap-2 p-0">
              {steps.map((step, index) => {
                const title = `${step.number.trim() || "?"}. ${step.name.trim() || `Activity ${index + 1}`}`;
                const performer = names.get(step.performing) ?? (step.performing || "no system yet");
                const panelId = `${base}-step-${step.key}-panel`;
                const label = (what: string) => <><span className="sr-only">Activity {index + 1}: </span>{what}</>;
                return (
                  <li key={step.key} className="border-line rounded-md border border-solid">
                    <button type="button" aria-expanded={step.open} aria-controls={panelId}
                      className="text-body text-ink flex min-h-11 w-full cursor-pointer items-center gap-2 border-0 bg-transparent px-3 py-2 text-left"
                      onClick={() => updateStep(step.key, { open: !step.open })}>
                      <ChevronRight size={16} aria-hidden="true" className={cx("shrink-0 transition-transform motion-reduce:transition-none", step.open && "rotate-90")} />
                      <span className="min-w-0 flex-1 break-words">{title}</span>
                      <span className="text-meta text-ink-muted">{performer}</span>
                    </button>
                    {step.open && (
                      <div id={panelId} className="border-line grid gap-3 border-0 border-t border-solid p-3">
                        <div className="grid gap-3 sm:grid-cols-[8rem_minmax(0,1fr)]">
                          <Input label={label("Number")} required value={step.number} {...field(`step-${step.key}-number`)}
                            onChange={(event) => updateStep(step.key, { number: event.target.value })} />
                          <Input label={label("Name")} required value={step.name} {...field(`step-${step.key}-name`)}
                            onChange={(event) => updateStep(step.key, { name: event.target.value })} />
                        </div>
                        <div className="grid gap-3 sm:grid-cols-2">
                          <Input label={label("Phase")} value={step.phase} placeholder="Example: Capture"
                            onChange={(event) => updateStep(step.key, { phase: event.target.value })} />
                          <Input label={label("Track")} value={step.track} placeholder="Empty for the main track"
                            onChange={(event) => updateStep(step.key, { track: event.target.value })} />
                          <Select label={label("Performed by")} value={step.performing}
                            onChange={(event) => updateStep(step.key, { performing: event.target.value })}>
                            <option value="">Not stated</option>
                            {systems.map((system) => <option key={system.id} value={system.id}>{system.name}</option>)}
                          </Select>
                          <Input label={label("Mode")} value={step.mode} placeholder="Example: Automated"
                            onChange={(event) => updateStep(step.key, { mode: event.target.value })} />
                        </div>
                        <fieldset className="m-0 grid gap-2 border-0 p-0">
                          <legend className="text-label text-ink mb-1 p-0">Supported by</legend>
                          {step.supporting.length > 0 && (
                            <ul role="list" className="m-0 flex list-none flex-wrap gap-2 p-0">
                              {step.supporting.map((systemId) => (
                                <li key={systemId}>
                                  <Button size="sm" variant="ghost" icon={<X size={14} aria-hidden="true" />}
                                    aria-label={`Remove ${names.get(systemId) ?? systemId} from activity ${index + 1}`}
                                    onClick={() => updateStep(step.key, { supporting: step.supporting.filter((item) => item !== systemId) })}>
                                    {names.get(systemId) ?? systemId}
                                  </Button>
                                </li>
                              ))}
                            </ul>
                          )}
                          <Select label={label("Add a supporting system")} value=""
                            onChange={(event) => event.target.value && updateStep(step.key, {
                              supporting: [...step.supporting, event.target.value],
                            })}>
                            <option value="">Choose a system</option>
                            {systems.filter((system) => system.id !== step.performing && !step.supporting.includes(system.id))
                              .map((system) => <option key={system.id} value={system.id}>{system.name}</option>)}
                          </Select>
                        </fieldset>
                        <Input label={label("System function")} value={step.system_function}
                          placeholder="Example: Offer UI and basket"
                          onChange={(event) => updateStep(step.key, { system_function: event.target.value })} />
                        <Textarea label={label("Description")} rows={2} dir="auto" value={step.description}
                          onChange={(event) => updateStep(step.key, { description: event.target.value })} />
                        <div className="grid gap-3 sm:grid-cols-2">
                          <Input label={label("Input")} value={step.input}
                            onChange={(event) => updateStep(step.key, { input: event.target.value })} />
                          <Input label={label("Output")} value={step.output}
                            onChange={(event) => updateStep(step.key, { output: event.target.value })} />
                          <Input label={label("eTOM")} value={step.etom}
                            placeholder="Example: Customer Relationship Management › Order Capture"
                            onChange={(event) => updateStep(step.key, { etom: event.target.value })} />
                          <Select label={label("Customer sees it")} value={step.customer_visible}
                            onChange={(event) => updateStep(step.key, { customer_visible: event.target.value })}>
                            <option value="">Not stated</option><option value="yes">Yes</option><option value="no">No</option>
                          </Select>
                          <Select label={label("Confidence")} value={step.confidence}
                            onChange={(event) => updateStep(step.key, { confidence: event.target.value as SourceConfidence | "" })}>
                            <option value="">Not stated</option>
                            {CONFIDENCES.map((item) => <option key={item} value={item}>{CONFIDENCE_LABEL[item].label}</option>)}
                          </Select>
                        </div>
                        {(offering?.components ?? []).length > 0 && (
                          <fieldset className="m-0 flex flex-wrap gap-x-4 gap-y-1 border-0 p-0">
                            <legend className="text-label text-ink mb-1 p-0">Components it works on</legend>
                            {offering?.components?.map((part) => (
                              <Checkbox key={part.id} label={part.name} checked={step.components.includes(part.id)}
                                onChange={(event) => updateStep(step.key, {
                                  components: event.target.checked
                                    ? [...step.components, part.id]
                                    : step.components.filter((item) => item !== part.id),
                                })} />
                            ))}
                          </fieldset>
                        )}
                        <Button size="sm" variant="ghost" className="w-fit" icon={<Trash2 size={14} aria-hidden="true" />}
                          onClick={() => setSteps((current) => current.filter((item) => item.key !== step.key))}>
                          Remove {title}
                        </Button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
            <Button size="sm" className="w-fit" icon={<Plus size={14} aria-hidden="true" />}
              onClick={() => setSteps((current) => [...current, {
                key: next(), original: null, open: true, number: "", name: "", phase: "", track: "", performing: "",
                supporting: [], system_function: "", mode: "", customer_visible: "", description: "", components: [],
                input: "", output: "", etom: "", confidence: "",
              }])}>
              Add activity
            </Button>
          </Section>

          <Section id={`${base}-rules`} title={`Exceptions and side tracks (${rules.length})`}
            description="Where the flow leaves an activity other than for the next one on the main track: a decision, a loop back, or parallel tracks that rejoin.">
            {rules.length === 0 && <p className="text-body text-ink-muted m-0">No rules: the flow runs straight down the main track.</p>}
            <ol className="m-0 grid list-none gap-3 p-0">
              {rules.map((rule, index) => {
                const label = (what: string) => <><span className="sr-only">Rule {index + 1}: </span>{what}</>;
                return (
                  <li key={rule.key} className="border-line grid gap-3 rounded-md border border-solid p-3">
                    <div className="grid gap-3 sm:grid-cols-3">
                      <Select label={label("Kind")} value={rule.kind}
                        onChange={(event) => updateRule(rule.key, { kind: event.target.value as FlowRuleKind })}>
                        {RULE_KINDS.map((kind) => <option key={kind} value={kind}>{RULE_LABEL[kind]}</option>)}
                      </Select>
                      {activitySelect(label("From"), rule.from, `rule-${rule.key}-from`, (value) => updateRule(rule.key, { from: value }))}
                      {activitySelect(label("To"), rule.to, `rule-${rule.key}-to`, (value) => updateRule(rule.key, { to: value }))}
                      <Input label={label("When")} value={rule.condition} placeholder="Example: FAIL"
                        onChange={(event) => updateRule(rule.key, { condition: event.target.value })} />
                      <Input label={label("Branch")} value={rule.branch} placeholder="Example: FIELD"
                        onChange={(event) => updateRule(rule.key, { branch: event.target.value })} />
                      {rule.kind === "parallel" && activitySelect(label("Rejoins at"), rule.rejoin_at, null,
                        (value) => updateRule(rule.key, { rejoin_at: value }), "Does not rejoin")}
                    </div>
                    <Button size="sm" variant="ghost" className="w-fit" icon={<Trash2 size={14} aria-hidden="true" />}
                      onClick={() => setRules((current) => current.filter((item) => item.key !== rule.key))}>
                      Remove rule {index + 1}
                    </Button>
                  </li>
                );
              })}
            </ol>
            <Button size="sm" className="w-fit" icon={<Plus size={14} aria-hidden="true" />} disabled={numbers.length < 2}
              onClick={() => setRules((current) => [...current, {
                key: next(), original: null, kind: "decision", from: "", to: "", condition: "", branch: "",
                parallel_group: "", rejoin_at: "",
              }])}>
              Add rule
            </Button>
          </Section>

          <Section id={`${base}-links`} title={`Integrations (${links.length})`}
            description="How one activity hands over to another: the interaction, the interface and what it carries.">
            {links.length === 0 && <p className="text-body text-ink-muted m-0">No integrations yet.</p>}
            <ol className="m-0 grid list-none gap-3 p-0">
              {links.map((link, index) => {
                const label = (what: string) => <><span className="sr-only">Integration {index + 1}: </span>{what}</>;
                return (
                  <li key={link.key} className="border-line grid gap-3 rounded-md border border-solid p-3">
                    <div className="grid gap-3 sm:grid-cols-2">
                      {activitySelect(label("From"), link.from, `link-${link.key}-from`, (value) => updateLink(link.key, { from: value }))}
                      {activitySelect(label("To"), link.to, `link-${link.key}-to`, (value) => updateLink(link.key, { to: value }))}
                      <Input label={label("Interaction")} value={link.interaction} placeholder="Example: API"
                        onChange={(event) => updateLink(link.key, { interaction: event.target.value })} />
                      <Input label={label("Interface")} value={link.interface}
                        onChange={(event) => updateLink(link.key, { interface: event.target.value })} />
                      <Input label={label("Payload")} value={link.payload}
                        onChange={(event) => updateLink(link.key, { payload: event.target.value })} />
                      <Input label={label("Timing")} value={link.timing} placeholder="Example: Sync"
                        onChange={(event) => updateLink(link.key, { timing: event.target.value })} />
                      <Input label={label("Correlation key")} value={link.correlation_key}
                        onChange={(event) => updateLink(link.key, { correlation_key: event.target.value })} />
                    </div>
                    <Button size="sm" variant="ghost" className="w-fit" icon={<Trash2 size={14} aria-hidden="true" />}
                      onClick={() => setLinks((current) => current.filter((item) => item.key !== link.key))}>
                      Remove integration {index + 1}
                    </Button>
                  </li>
                );
              })}
            </ol>
            <Button size="sm" className="w-fit" icon={<Plus size={14} aria-hidden="true" />} disabled={numbers.length < 2}
              onClick={() => setLinks((current) => [...current, {
                key: next(), original: null, from: "", to: "", interaction: "", interface: "", payload: "", timing: "",
                correlation_key: "",
              }])}>
              Add integration
            </Button>
          </Section>
        </div>

        <div className="bg-surface-raised border-line sticky -bottom-6 z-[var(--z-sticky)] -mx-6 -mb-6 border-0 border-t border-solid px-6 pb-6">
          {error && <ErrorNotice message={error} />}
          <ModalFooter className="mt-4">
            <p className="text-meta text-ink-muted m-0 mr-auto">Saves to this version in progress, not the published catalogue.</p>
            <Button onClick={requestClose}>Cancel</Button>
            <Button type="submit" variant="primary" loading={saving} loadingLabel="Saving…">{saveLabel}</Button>
          </ModalFooter>
        </div>
      </form>
      {confirmingDiscard && (
        <ConfirmDialog
          title={creating ? "Discard this new journey?" : `Discard changes to ${initial.name}?`}
          message="What you changed in this drawer has not been saved and will be lost."
          confirmLabel="Discard changes"
          onCancel={() => setConfirmingDiscard(false)}
          onConfirm={onCancel}
        />
      )}
    </Modal>
  );
}
