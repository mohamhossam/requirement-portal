import type { Organisation, Product, Squad, ValueStream } from "../../api/organisation";

export type Ownership = { squads: Squad[]; valueStreams: ValueStream[]; products: Product[] };

const byName = <T extends { name: string }>(a: T, b: T) => a.name.localeCompare(b.name);

/**
 * Who owns a system, by the same rule as the server's `OrganisationCatalogue.ownership`:
 * the squads with a seat for it, the products that link it, and the value streams
 * of both.
 */
export function ownershipOf(systemId: string, organisation: Organisation): Ownership {
  const squads = organisation.squads
    .filter((squad) => (squad.systems ?? []).some((item) => item.system_id === systemId))
    .sort(byName);
  const products = organisation.products
    .filter((product) => (product.system_ids ?? []).includes(systemId))
    .sort(byName);
  const streamIds = new Set([...squads, ...products].map((item) => item.value_stream_id));
  const valueStreams = organisation.value_streams.filter((stream) => streamIds.has(stream.id)).sort(byName);
  return { squads, valueStreams, products };
}
