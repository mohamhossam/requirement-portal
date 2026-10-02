import { apiRequest } from "./client";
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Person = Schemas["PersonSchema"];
export type ValueStream = Schemas["ValueStreamSchema"];
export type Product = Schemas["ProductSchema"];
export type Squad = Schemas["SquadSchema"];
export type SquadSystem = Schemas["SquadSystemSchema"];
export type Organisation = Schemas["OrganisationResponse"];
export type OrganisationAuditEvent = Schemas["OrganisationAuditEventResponse"];

const root = "/organisation";

type Kind = "people" | "value-streams" | "products" | "squads";
const bodyKey: Record<Kind, string> = {
  people: "person", "value-streams": "value_stream", products: "product", squads: "squad",
};

/**
 * Create when `expectedRevision` is absent, otherwise update that revision. Every
 * write answers with the whole catalogue, so a screen never holds a stale half.
 */
function save<T extends { id: string }>(kind: Kind, record: T, expectedRevision?: number) {
  const creating = expectedRevision === undefined;
  return apiRequest<Organisation>(
    creating ? `${root}/${kind}` : `${root}/${kind}/${encodeURIComponent(record.id)}`,
    {
      method: creating ? "POST" : "PUT",
      body: JSON.stringify({ expected_revision: expectedRevision ?? null, [bodyKey[kind]]: record }),
    },
  );
}

function remove(kind: Exclude<Kind, "people">, id: string, expectedRevision: number) {
  return apiRequest<Organisation>(`${root}/${kind}/${encodeURIComponent(id)}`, {
    method: "DELETE",
    body: JSON.stringify({ expected_revision: expectedRevision }),
  });
}

export const organisationApi = {
  get: () => apiRequest<Organisation>(root),
  audit: () => apiRequest<OrganisationAuditEvent[]>(`${root}/audit`),
  savePerson: (person: Person, expectedRevision?: number) => save("people", person, expectedRevision),
  saveValueStream: (stream: ValueStream, expectedRevision?: number) =>
    save("value-streams", stream, expectedRevision),
  saveProduct: (product: Product, expectedRevision?: number) => save("products", product, expectedRevision),
  saveSquad: (squad: Squad, expectedRevision?: number) => save("squads", squad, expectedRevision),
  removeValueStream: (id: string, expectedRevision: number) => remove("value-streams", id, expectedRevision),
  removeProduct: (id: string, expectedRevision: number) => remove("products", id, expectedRevision),
  removeSquad: (id: string, expectedRevision: number) => remove("squads", id, expectedRevision),
};

/** A readable, stable id from a name, unique against the ids already taken. */
export function newId(name: string, taken: Iterable<string>): string {
  const base = name.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "item";
  const used = new Set(taken);
  let candidate = base;
  for (let suffix = 2; used.has(candidate); suffix += 1) candidate = `${base}-${suffix}`;
  return candidate;
}
