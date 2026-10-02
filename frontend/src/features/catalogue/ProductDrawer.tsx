import { Lock, Plus, Trash2, X } from "lucide-react";
import { useId, useRef, useState, type FormEvent, type ReactNode } from "react";

import type {
  ComponentResponsibility, OfferingComponent, OfferingPoint, OrderType, ProductOffering, SourceConfidence,
} from "../../api/knowledge";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Button, Checkbox, Input, Modal, ModalFooter, ModalHeader, Select, Textarea } from "../../components/ui";
import { CONFIDENCES, CONFIDENCE_LABEL, slug } from "./labels";

type OrderRow = { key: number; original: OrderType | null; code: string; name: string; enabled: boolean; description: string };
type DutyRow = {
  key: number; original: ComponentResponsibility | null; system_id: string; role: string; description: string;
  order_types: string[]; confidence: SourceConfidence | "";
};
type PartRow = {
  key: number; original: OfferingComponent | null; id: string; idTouched: boolean; name: string; code: string;
  kind: string; mandatory: string; customer_visible: string; description: string; commercial_spec: string;
  technical_spec: string; technical_details: string; confidence: SourceConfidence | ""; duties: DutyRow[];
};
type PointRow = { key: number; original: OfferingPoint | null; name: string; description: string };
type Errors = Record<string, string>;

const flag = (value: boolean | null | undefined) => (value == null ? "" : value ? "yes" : "no");
const unflag = (value: string) => (value === "" ? null : value === "yes");
const text = (value: string) => value.trim() || null;

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

function ConfidenceSelect({ label, value, onChange }: {
  label: ReactNode; value: SourceConfidence | ""; onChange: (value: SourceConfidence | "") => void;
}) {
  return (
    <Select label={label} value={value} onChange={(event) => onChange(event.target.value as SourceConfidence | "")}>
      <option value="">Not stated</option>
      {CONFIDENCES.map((item) => <option key={item} value={item}>{CONFIDENCE_LABEL[item].label}</option>)}
    </Select>
  );
}

/**
 * Add or edit one product offering in a version in progress (ADR-0095).
 *
 * Five parts, each a heading a person can jump to: what the offering is, how it
 * is ordered, the components it is made of with the systems that deliver each,
 * what it gives customers, and who it is for. Facts the drawer does not show,
 * such as where an order type was sourced, are kept as they were.
 */
export function ProductDrawer({
  initial, systems, taken, creating, saving, error, onSave, onCancel, title, saveLabel = "Save offering",
}: {
  initial: ProductOffering;
  systems: { id: string; name: string }[];
  /** Offering ids already used, so a new one gets its own. */
  taken: string[];
  creating: boolean;
  saving: boolean;
  error: string | null;
  onSave: (offering: ProductOffering) => void;
  onCancel: () => void;
  /** In place of "Edit <name>", when the drawer corrects a suggestion before it is accepted. */
  title?: string;
  saveLabel?: string;
}) {
  const base = useId();
  const titleId = `${base}-title`;
  // Rows that arrive with the offering are keyed by position; rows added here count on
  // from far above, so the two never meet.
  const counter = useRef(1_000_000);
  const next = () => (counter.current += 1);

  const [name, setName] = useState(initial.name);
  const [id, setId] = useState(initial.id);
  const [idTouched, setIdTouched] = useState(!creating);
  const [code, setCode] = useState(initial.code ?? "");
  const [family, setFamily] = useState(initial.family ?? "");
  const [version, setVersion] = useState(initial.version ?? "");
  const [lifecycle, setLifecycle] = useState(initial.lifecycle ?? "");
  const [proposition, setProposition] = useState(initial.proposition ?? "");
  const [rules, setRules] = useState((initial.rules ?? []).join("\n"));
  const [confidence, setConfidence] = useState<SourceConfidence | "">(initial.confidence ?? "");
  const [source, setSource] = useState(initial.source ?? "");
  const [orders, setOrders] = useState<OrderRow[]>(() => (initial.order_types ?? []).map((order, index) => ({
    key: index, original: order, code: order.code, name: order.name, enabled: order.enabled ?? true,
    description: order.description ?? "",
  })));
  const [parts, setParts] = useState<PartRow[]>(() => (initial.components ?? []).map((part, index) => ({
    key: 1_000 + index, original: part, id: part.id, idTouched: true, name: part.name, code: part.code ?? "",
    kind: part.kind ?? "", mandatory: flag(part.mandatory), customer_visible: flag(part.customer_visible),
    description: part.description ?? "", commercial_spec: part.commercial_spec ?? "",
    technical_spec: part.technical_spec ?? "", technical_details: part.technical_details ?? "",
    confidence: part.confidence ?? "",
    duties: (part.responsibilities ?? []).map((duty, number) => ({
      key: 100_000 + index * 1_000 + number, original: duty, system_id: duty.system_id, role: duty.role, description: duty.description,
      order_types: duty.order_types ?? [], confidence: duty.confidence ?? "",
    })),
  })));
  const points = (items: OfferingPoint[] | undefined, start: number): PointRow[] => (items ?? []).map((point, index) => ({
    key: start + index, original: point, name: point.name, description: point.description ?? "",
  }));
  const [values, setValues] = useState<PointRow[]>(() => points(initial.values, 500_000));
  const [audiences, setAudiences] = useState<PointRow[]>(() => points(initial.audiences, 600_000));
  const [errors, setErrors] = useState<Errors>({});
  const [confirmingDiscard, setConfirmingDiscard] = useState(false);

  const updatePart = (key: number, changes: Partial<PartRow>) =>
    setParts((current) => current.map((part) => (part.key === key ? { ...part, ...changes } : part)));
  const updateDuty = (partKey: number, dutyKey: number, changes: Partial<DutyRow>) =>
    setParts((current) => current.map((part) => (part.key !== partKey ? part : {
      ...part, duties: part.duties.map((duty) => (duty.key === dutyKey ? { ...duty, ...changes } : duty)),
    })));

  const offering = (): ProductOffering => ({
    ...initial,
    id: id.trim(), name: name.trim(), code: text(code), family: text(family), version: text(version),
    lifecycle: text(lifecycle), proposition: text(proposition),
    rules: rules.split("\n").map((rule) => rule.trim()).filter(Boolean),
    confidence: confidence || null, source: text(source),
    order_types: orders.map((order) => ({
      ...(order.original ?? {}), code: order.code.trim(), name: order.name.trim(), enabled: order.enabled,
      description: text(order.description),
    })),
    components: parts.map((part) => ({
      ...(part.original ?? {}), id: part.id.trim(), name: part.name.trim(), code: text(part.code), kind: text(part.kind),
      mandatory: unflag(part.mandatory), customer_visible: unflag(part.customer_visible),
      description: text(part.description), commercial_spec: text(part.commercial_spec),
      technical_spec: text(part.technical_spec), technical_details: text(part.technical_details),
      confidence: part.confidence || null,
      responsibilities: part.duties.map((duty) => ({
        ...(duty.original ?? {}), system_id: duty.system_id, role: duty.role.trim(), description: duty.description.trim(),
        order_types: duty.order_types.filter((code) => orders.some((order) => order.code.trim() === code)),
        confidence: duty.confidence || null,
      })),
    })),
    values: values.map((point) => ({ ...(point.original ?? {}), name: point.name.trim(), description: text(point.description) })),
    audiences: audiences.map((point) => ({ ...(point.original ?? {}), name: point.name.trim(), description: text(point.description) })),
  });
  // The form as it opened, taken on the first render, so an unsaved change can be told from none.
  const [baseline] = useState(() => JSON.stringify(offering()));
  const dirty = JSON.stringify(offering()) !== baseline;
  const requestClose = () => (dirty ? setConfirmingDiscard(true) : onCancel());

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    if (!name.trim()) found.name = "Give the offering a name.";
    if (creating && !id.trim()) found.id = "Give the offering an ID.";
    else if (creating && taken.includes(id.trim())) found.id = "Another offering has this ID.";
    for (const order of orders) {
      if (!order.code.trim()) found[`order-${order.key}-code`] = "Give the order type a code.";
      if (!order.name.trim()) found[`order-${order.key}-name`] = "Give the order type a name.";
    }
    for (const part of parts) {
      if (!part.name.trim()) found[`part-${part.key}-name`] = "Give the component a name.";
      if (!part.id.trim()) found[`part-${part.key}-id`] = "Give the component an ID.";
      for (const duty of part.duties) {
        if (!duty.system_id) found[`duty-${duty.key}-system`] = "Choose the system.";
        if (!duty.role.trim()) found[`duty-${duty.key}-role`] = "Say the system's role.";
        if (!duty.description.trim()) found[`duty-${duty.key}-description`] = "Say what the system does.";
      }
    }
    for (const [list, kind] of [[values, "value"], [audiences, "audience"]] as const) {
      for (const point of list) if (!point.name.trim()) found[`${kind}-${point.key}-name`] = "Give it a name.";
    }
    setErrors(found);
    const first = Object.keys(found)[0];
    if (first) {
      document.getElementById(`${base}-${first}`)?.focus();
      return;
    }
    onSave(offering());
  };
  const field = (key: string) => ({ id: `${base}-${key}`, error: errors[key] });
  const orderCodes = orders.map((order) => order.code.trim()).filter(Boolean);
  const pointList = (kind: "value" | "audience", rows: PointRow[], setRows: (rows: PointRow[]) => void, noun: string) => (
    <>
      {rows.length === 0 && <p className="text-body text-ink-muted m-0">None yet.</p>}
      <ol className="m-0 grid list-none gap-3 p-0">
        {rows.map((point, index) => (
          <li key={point.key} className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto] sm:items-start">
            <Input label={<>{noun} {index + 1}<span className="sr-only">, name</span></>} required value={point.name}
              {...field(`${kind}-${point.key}-name`)}
              onChange={(event) => setRows(rows.map((item) => (item.key === point.key ? { ...item, name: event.target.value } : item)))} />
            <Input label={<><span className="sr-only">{noun} {index + 1} </span>Description</>} value={point.description}
              onChange={(event) => setRows(rows.map((item) => (item.key === point.key ? { ...item, description: event.target.value } : item)))} />
            <Button size="icon" variant="ghost" className="mt-6 min-h-9 min-w-9" aria-label={`Remove ${noun.toLowerCase()} ${index + 1}`}
              icon={<Trash2 size={16} aria-hidden="true" />} onClick={() => setRows(rows.filter((item) => item.key !== point.key))} />
          </li>
        ))}
      </ol>
      <Button size="sm" className="w-fit" icon={<Plus size={14} aria-hidden="true" />}
        onClick={() => setRows([...rows, { key: next(), original: null, name: "", description: "" }])}>
        Add {noun.toLowerCase()}
      </Button>
    </>
  );

  return (
    <Modal variant="drawer" side="right" size="lg" labelledBy={titleId} onClose={requestClose}
      closeOnOutsideClick={!dirty} className="[scroll-padding-top:8rem] [scroll-padding-bottom:6rem]">
      <form onSubmit={submit} noValidate className="grid min-h-full grid-rows-[auto_1fr_auto]">
        <div className="bg-surface-raised border-line sticky -top-6 z-[var(--z-sticky)] -mx-6 -mt-6 border-0 border-b border-solid px-6 pt-6">
          <div className="pr-10">
            <ModalHeader id={titleId} eyebrow={creating ? "New product offering" : "Product offering"}
              title={title ?? (creating ? "Add a product offering" : `Edit ${initial.name}`)}
              description={<span className="text-meta">
                {`${orders.length} order ${orders.length === 1 ? "type" : "types"} · ${parts.length} ${parts.length === 1 ? "component" : "components"}`}
              </span>} />
          </div>
          <Button size="icon" variant="ghost" className="absolute top-5 right-5" aria-label="Close"
            icon={<X size={18} aria-hidden="true" />} onClick={requestClose} />
        </div>

        <div className="text-body text-ink-soft grid content-start gap-6 py-6 [&>section+section]:[border-top:1px_solid_var(--line)] [&>section+section]:pt-6">
          <Section id={`${base}-about`} title="The offering">
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="Name" required value={name} autoComplete="off" {...field("name")}
                onChange={(event) => {
                  setName(event.target.value);
                  if (creating && !idTouched) setId(slug(event.target.value, ""));
                }} />
              {creating ? (
                <Input label="Offering ID" required className="font-mono" value={id} autoComplete="off" {...field("id")}
                  hint="Filled in from the name. A short, stable key; it cannot change once saved."
                  onChange={(event) => { setId(event.target.value); setIdTouched(true); }} />
              ) : (
                <div className="grid gap-1">
                  <span className="text-label text-ink">Offering ID</span>
                  <p className="m-0 flex flex-wrap items-center gap-2">
                    <Lock className="text-ink-muted shrink-0" size={14} aria-hidden="true" />
                    <code className="text-body text-ink font-mono">{initial.id}</code>
                  </p>
                </div>
              )}
              <Input label="Code" className="font-mono" value={code} placeholder="Example: BUSINESS_PRO_PLUS"
                onChange={(event) => setCode(event.target.value)} />
              <Input label="Family" value={family} onChange={(event) => setFamily(event.target.value)} />
              <Input label="Version" value={version} onChange={(event) => setVersion(event.target.value)} />
              <Input label="Lifecycle" value={lifecycle} placeholder="Example: Reference"
                onChange={(event) => setLifecycle(event.target.value)} />
              <ConfidenceSelect label="Confidence" value={confidence} onChange={setConfidence} />
              <Input label="Source" value={source} placeholder="Example: Design document §3.1"
                onChange={(event) => setSource(event.target.value)} />
            </div>
            <Textarea label="Proposition" rows={3} dir="auto" value={proposition}
              hint="What the offering is, in a few sentences." onChange={(event) => setProposition(event.target.value)} />
            <Textarea label="Rules" rows={3} dir="auto" value={rules} hint="One rule per line."
              onChange={(event) => setRules(event.target.value)} />
          </Section>

          <Section id={`${base}-orders`} title={`Order types (${orders.length})`}
            description="How the offering is ordered, such as New Activation. Responsibilities can name the order types they apply to.">
            {orders.length === 0 && <p className="text-body text-ink-muted m-0">No order types yet.</p>}
            <ol className="m-0 grid list-none gap-3 p-0">
              {orders.map((order, index) => (
                <li key={order.key} className="border-line grid gap-3 rounded-md border border-solid p-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Input label={<>Order type {index + 1}<span className="sr-only">, name</span></>} required value={order.name}
                      {...field(`order-${order.key}-name`)}
                      onChange={(event) => setOrders((current) => current.map((item) => (item.key === order.key
                        ? { ...item, name: event.target.value } : item)))} />
                    <Input label={<><span className="sr-only">Order type {index + 1} </span>Code</>} required className="font-mono"
                      value={order.code} {...field(`order-${order.key}-code`)} placeholder="Example: NEW_ACTIVATION"
                      onChange={(event) => setOrders((current) => current.map((item) => (item.key === order.key ? { ...item, code: event.target.value } : item)))} />
                  </div>
                  <Input label={<><span className="sr-only">Order type {index + 1} </span>Description</>} value={order.description}
                    onChange={(event) => setOrders((current) => current.map((item) => (item.key === order.key ? { ...item, description: event.target.value } : item)))} />
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Checkbox label={<>Offered now<span className="sr-only"> (order type {index + 1})</span></>} checked={order.enabled}
                      onChange={(event) => setOrders((current) => current.map((item) => (item.key === order.key ? { ...item, enabled: event.target.checked } : item)))} />
                    <Button size="sm" variant="ghost" icon={<Trash2 size={14} aria-hidden="true" />}
                      onClick={() => setOrders((current) => current.filter((item) => item.key !== order.key))}>
                      Remove order type {index + 1}
                    </Button>
                  </div>
                </li>
              ))}
            </ol>
            <Button size="sm" className="w-fit" icon={<Plus size={14} aria-hidden="true" />}
              onClick={() => setOrders((current) => [...current, { key: next(), original: null, code: "", name: "", enabled: true, description: "" }])}>
              Add order type
            </Button>
          </Section>

          <Section id={`${base}-components`} title={`Components (${parts.length})`}
            description="The parts of the offering, and which systems deliver each one, in which role.">
            {parts.length === 0 && <p className="text-body text-ink-muted m-0">No components yet.</p>}
            <ol className="m-0 grid list-none gap-4 p-0">
              {parts.map((part, index) => {
                const label = part.name.trim() || `Component ${index + 1}`;
                return (
                  <li key={part.key} className="border-line grid gap-3 rounded-md border border-solid p-4">
                    <h4 className="text-body text-ink m-0 font-semibold">{label}</h4>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <Input label={<>Name<span className="sr-only"> of component {index + 1}</span></>} required value={part.name}
                        {...field(`part-${part.key}-name`)}
                        onChange={(event) => updatePart(part.key, {
                          name: event.target.value,
                          ...(part.idTouched ? {} : { id: slug(event.target.value, "") }),
                        })} />
                      <Input label={<>ID<span className="sr-only"> of component {index + 1}</span></>} required className="font-mono"
                        value={part.id} {...field(`part-${part.key}-id`)}
                        onChange={(event) => updatePart(part.key, { id: event.target.value, idTouched: true })} />
                      <Input label="Code" className="font-mono" value={part.code} onChange={(event) => updatePart(part.key, { code: event.target.value })} />
                      <Input label="Type" value={part.kind} placeholder="Example: Service"
                        onChange={(event) => updatePart(part.key, { kind: event.target.value })} />
                      <Select label="Mandatory" value={part.mandatory} onChange={(event) => updatePart(part.key, { mandatory: event.target.value })}>
                        <option value="">Not stated</option><option value="yes">Yes</option><option value="no">No</option>
                      </Select>
                      <Select label="Customer visible" value={part.customer_visible}
                        onChange={(event) => updatePart(part.key, { customer_visible: event.target.value })}>
                        <option value="">Not stated</option><option value="yes">Yes</option><option value="no">No</option>
                      </Select>
                      <Input label="Commercial spec" className="font-mono" value={part.commercial_spec}
                        onChange={(event) => updatePart(part.key, { commercial_spec: event.target.value })} />
                      <Input label="Technical spec" className="font-mono" value={part.technical_spec}
                        onChange={(event) => updatePart(part.key, { technical_spec: event.target.value })} />
                      <ConfidenceSelect label="Confidence" value={part.confidence} onChange={(value) => updatePart(part.key, { confidence: value })} />
                    </div>
                    <Textarea label="Description" rows={2} dir="auto" value={part.description}
                      onChange={(event) => updatePart(part.key, { description: event.target.value })} />
                    <Textarea label="Technical details" rows={2} dir="auto" value={part.technical_details}
                      onChange={(event) => updatePart(part.key, { technical_details: event.target.value })} />

                    <fieldset className="border-line m-0 grid gap-3 rounded-md border border-solid p-3">
                      <legend className="text-label text-ink px-1">Systems that deliver {label} ({part.duties.length})</legend>
                      {part.duties.length === 0 && <p className="text-meta text-ink-muted m-0">No systems yet.</p>}
                      {part.duties.map((duty, number) => (
                        <div key={duty.key} className="border-line grid gap-3 border-0 border-b border-solid pb-3 last:border-b-0 last:pb-0">
                          <div className="grid gap-3 sm:grid-cols-2">
                            <Select label={<><span className="sr-only">{label}, responsibility {number + 1}: </span>System</>} required
                              value={duty.system_id} {...field(`duty-${duty.key}-system`)}
                              onChange={(event) => updateDuty(part.key, duty.key, { system_id: event.target.value })}>
                              <option value="">Choose a system</option>
                              {systems.map((system) => <option key={system.id} value={system.id}>{system.name}</option>)}
                            </Select>
                            <Input label={<><span className="sr-only">{label}, responsibility {number + 1}: </span>Role</>} required
                              value={duty.role} placeholder="Example: Primary orchestrator" {...field(`duty-${duty.key}-role`)}
                              onChange={(event) => updateDuty(part.key, duty.key, { role: event.target.value })} />
                          </div>
                          <Input label={<><span className="sr-only">{label}, responsibility {number + 1}: </span>What it does</>} required
                            value={duty.description} {...field(`duty-${duty.key}-description`)}
                            onChange={(event) => updateDuty(part.key, duty.key, { description: event.target.value })} />
                          {orderCodes.length > 0 && (
                            <fieldset className="m-0 flex flex-wrap gap-x-4 gap-y-1 border-0 p-0">
                              <legend className="text-meta text-ink-muted mb-1 p-0">For order types (none means all)</legend>
                              {orderCodes.map((orderCode) => (
                                <Checkbox key={orderCode} label={orders.find((order) => order.code.trim() === orderCode)?.name || orderCode}
                                  checked={duty.order_types.includes(orderCode)}
                                  onChange={(event) => updateDuty(part.key, duty.key, {
                                    order_types: event.target.checked
                                      ? [...duty.order_types, orderCode]
                                      : duty.order_types.filter((item) => item !== orderCode),
                                  })} />
                              ))}
                            </fieldset>
                          )}
                          <div className="flex flex-wrap items-end justify-between gap-2">
                            <ConfidenceSelect label={<><span className="sr-only">{label}, responsibility {number + 1}: </span>Confidence</>}
                              value={duty.confidence} onChange={(value) => updateDuty(part.key, duty.key, { confidence: value })} />
                            <Button size="sm" variant="ghost" icon={<Trash2 size={14} aria-hidden="true" />}
                              onClick={() => updatePart(part.key, { duties: part.duties.filter((item) => item.key !== duty.key) })}>
                              Remove responsibility {number + 1}
                            </Button>
                          </div>
                        </div>
                      ))}
                      <Button size="sm" className="w-fit" icon={<Plus size={14} aria-hidden="true" />}
                        onClick={() => updatePart(part.key, { duties: [...part.duties, {
                          key: next(), original: null, system_id: "", role: "", description: "", order_types: [], confidence: "",
                        }] })}>
                        Add a system to {label}
                      </Button>
                    </fieldset>
                    <Button size="sm" variant="ghost" className="w-fit" icon={<Trash2 size={14} aria-hidden="true" />}
                      onClick={() => setParts((current) => current.filter((item) => item.key !== part.key))}>
                      Remove {label}
                    </Button>
                  </li>
                );
              })}
            </ol>
            <Button size="sm" className="w-fit" icon={<Plus size={14} aria-hidden="true" />}
              onClick={() => setParts((current) => [...current, {
                key: next(), original: null, id: "", idTouched: false, name: "", code: "", kind: "", mandatory: "",
                customer_visible: "", description: "", commercial_spec: "", technical_spec: "", technical_details: "",
                confidence: "", duties: [],
              }])}>
              Add component
            </Button>
          </Section>

          <Section id={`${base}-values`} title={`Customer value (${values.length})`}
            description="What the offering gives its customers.">
            {pointList("value", values, setValues, "Value")}
          </Section>

          <Section id={`${base}-audiences`} title={`Who it is for (${audiences.length})`}
            description="The kinds of customer the offering suits.">
            {pointList("audience", audiences, setAudiences, "Audience")}
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
          title={creating ? "Discard this new offering?" : `Discard changes to ${initial.name}?`}
          message="What you changed in this drawer has not been saved and will be lost."
          confirmLabel="Discard changes"
          onCancel={() => setConfirmingDiscard(false)}
          onConfirm={onCancel}
        />
      )}
    </Modal>
  );
}
