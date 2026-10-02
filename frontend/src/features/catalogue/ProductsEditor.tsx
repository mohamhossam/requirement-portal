import { useMutation } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { errorMessage } from "../../api/errors";
import { knowledgeApi, type KnowledgeRelease, type ProductOffering } from "../../api/knowledge";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Button } from "../../components/ui";
import { ProductDrawer } from "./ProductDrawer";

const EMPTY: ProductOffering = {
  id: "", name: "", rules: [], order_types: [], components: [], values: [], audiences: [],
};

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/**
 * The version's product offerings (ADR-0095), added and edited by hand. Each
 * opens in a drawer; removing one asks first, since its components and
 * responsibilities go with it.
 */
export function ProductsEditor({ draft, onChanged }: { draft: KnowledgeRelease; onChanged: () => void }) {
  const offerings = draft.products ?? [];
  const [editing, setEditing] = useState<{ offering: ProductOffering; creating: boolean } | null>(null);
  const [removing, setRemoving] = useState<ProductOffering | null>(null);
  const [status, setStatus] = useState("");
  const save = useMutation({
    mutationFn: knowledgeApi.save,
    onSuccess: () => {
      setEditing(null);
      setRemoving(null);
      onChanged();
    },
  });
  const saveOfferings = (next: ProductOffering[], done: string) =>
    save.mutate({ ...draft, products: next }, { onSuccess: () => setStatus(done) });
  const systems = [...draft.systems].sort((a, b) => a.name.localeCompare(b.name))
    .map((system) => ({ id: system.id, name: system.name }));

  return (
    <section className="grid min-w-0 gap-3" aria-labelledby="offerings-editor-title">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid gap-1">
          <h4 className="text-body text-ink m-0 font-semibold" id="offerings-editor-title" tabIndex={-1}>
            Product offerings ({offerings.length})
          </h4>
          <p className="text-meta text-ink-muted m-0 max-w-[68ch]">
            Commercial offerings, how they are ordered, and which systems deliver each of their components.
          </p>
        </div>
        <Button icon={<Plus size={16} aria-hidden="true" />}
          onClick={() => { save.reset(); setEditing({ offering: EMPTY, creating: true }); }}>
          Add product offering
        </Button>
      </header>
      {save.error && !editing && <ErrorNotice message={errorMessage(save.error)} />}
      {status && <p className="text-meta text-ink-soft m-0" role="status">{status}</p>}
      {offerings.length === 0 ? (
        <p className="text-body text-ink-muted m-0">No product offerings yet.</p>
      ) : (
        <ul role="list" className="border-line m-0 grid list-none rounded-md border border-solid p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">
          {[...offerings].sort((a, b) => a.name.localeCompare(b.name)).map((offering) => {
            const parts = offering.components ?? [];
            const duties = parts.reduce((count, part) => count + (part.responsibilities ?? []).length, 0);
            return (
              <li key={offering.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                <span className="grid min-w-0 flex-1 gap-0.5">
                  <span className="text-body text-ink">
                    {offering.name}
                    {offering.code && <span className="text-meta text-ink-muted font-mono"> · {offering.code}</span>}
                  </span>
                  <span className="text-meta text-ink-muted">
                    {[plural((offering.order_types ?? []).length, "order type", "order types"),
                      plural(parts.length, "component", "components"),
                      plural(duties, "system responsibility", "system responsibilities")].join(" · ")}
                  </span>
                </span>
                <span className="flex flex-wrap gap-1">
                  <Button size="sm" variant="ghost" icon={<Pencil size={14} aria-hidden="true" />}
                    aria-label={`Edit ${offering.name}`}
                    onClick={() => { save.reset(); setEditing({ offering, creating: false }); }}>
                    Edit
                  </Button>
                  <Button size="sm" variant="ghost" icon={<Trash2 size={14} aria-hidden="true" />}
                    disabled={save.isPending} aria-label={`Remove ${offering.name}`}
                    onClick={() => setRemoving(offering)}>
                    Remove
                  </Button>
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {editing && (
        <ProductDrawer
          initial={editing.offering}
          systems={systems}
          taken={offerings.map((item) => item.id)}
          creating={editing.creating}
          saving={save.isPending}
          error={save.error ? errorMessage(save.error) : null}
          onSave={(offering) => saveOfferings(editing.creating
            ? [...offerings, offering]
            : offerings.map((item) => (item.id === offering.id ? offering : item)),
          `${editing.creating ? "Added" : "Saved"} ${offering.name}.`)}
          onCancel={() => setEditing(null)}
        />
      )}
      {removing && (
        <ConfirmDialog
          title={`Remove ${removing.name}?`}
          message="Its order types, components and their system responsibilities are removed from this version too."
          confirmLabel="Remove offering"
          onCancel={() => setRemoving(null)}
          onConfirm={() => saveOfferings(offerings.filter((item) => item.id !== removing.id),
            `Removed ${removing.name}.`)}
        />
      )}
    </section>
  );
}
