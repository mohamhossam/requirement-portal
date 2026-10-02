import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { knowledgeApi, type KnowledgeRelease } from "../../api/knowledge";
import { newId, organisationApi, type Organisation } from "../../api/organisation";
import { renderWithClient } from "../../test/renderWithClient";
import { SquadCataloguePage } from "./SquadCataloguePage";

type Actor = Awaited<ReturnType<typeof knowledgeApi.me>>;

const maintainer = { id: "editor", display_name: "Kim Editor", roles: ["knowledge_maintainer"] };
const reader = { ...maintainer, roles: ["knowledge_reader"] };

const active: KnowledgeRelease = {
  id: "published-1", revision: 1, status: "published", built_revision: 1,
  published_at: "2026-09-01T09:00:00Z", published_by: "amina", index_profile: null, index_hash: null,
  systems: [
    { id: "bcrm", name: "BCRM", name_ar: null, aliases: [], capabilities: [], constraints: [] },
    { id: "gis", name: "GIS", name_ar: null, aliases: [], capabilities: [], constraints: [] },
  ],
  relationships: [],
  documents: [],
};

const organisation: Organisation = {
  people: [
    { id: "layla", name: "Layla Lead", email: "layla@example.test", team: "Delivery", active: true, revision: 1 },
    { id: "sam", name: "Sam Scrum", email: null, team: "Agile office", active: true, revision: 1 },
    { id: "bea", name: "Bea Backend", email: null, team: "CRM team", active: true, revision: 1 },
  ],
  value_streams: [{ id: "retail", name: "Retail", lead_person_id: "layla", revision: 1 }],
  products: [{ id: "ordering", value_stream_id: "retail", name: "Ordering", description: "Order capture",
    system_ids: ["bcrm", "retired"], revision: 1 }],
  squads: [{ id: "sales", name: "Sales squad", value_stream_id: "retail", scrum_master_person_id: "sam",
    systems: [{ system_id: "bcrm", person_id: "bea" }, { system_id: "gis", person_id: null }], revision: 2 }],
};

function renderPage() {
  return renderWithClient(<MemoryRouter><SquadCataloguePage /></MemoryRouter>);
}

beforeEach(() => {
  vi.spyOn(knowledgeApi, "me").mockResolvedValue(maintainer as unknown as Actor);
  vi.spyOn(knowledgeApi, "active").mockResolvedValue(active);
  vi.spyOn(organisationApi, "get").mockResolvedValue(organisation);
});

afterEach(() => vi.restoreAllMocks());

it("shows each value stream with its lead, products and squads", async () => {
  renderPage();

  const stream = await screen.findByRole("article", { name: "Retail" });
  expect(within(stream).getByText("Layla Lead")).toBeVisible();
  expect(within(stream).getByText("Order capture")).toBeVisible();
  expect(within(stream).getByText("retired (not in the catalogue in use)")).toBeVisible();
  const squad = within(stream).getByRole("region", { name: "Sales squad" });
  expect(within(squad).getByText("Sam Scrum", { exact: false })).toBeVisible();
  const [, staffed, unstaffed] = within(squad).getAllByRole("row");
  if (!staffed || !unstaffed) throw new Error("Expected two system rows.");
  expect(within(staffed).getByText("Bea Backend")).toBeVisible();
  expect(within(staffed).getByText("CRM team")).toBeVisible();
  expect(within(unstaffed).getByText("Resource needed")).toBeVisible();
});

it("adds a squad with a scrum master and one resource per system", async () => {
  const save = vi.spyOn(organisationApi, "saveSquad").mockResolvedValue(organisation);

  renderPage();

  const stream = await screen.findByRole("article", { name: "Retail" });
  await userEvent.click(within(stream).getByRole("button", { name: "Add squad" }));
  const dialog = await screen.findByRole("dialog");
  await userEvent.type(within(dialog).getByLabelText(/Squad name/), "Care squad");
  await userEvent.selectOptions(within(dialog).getByLabelText("Scrum master"), "sam");
  await userEvent.click(within(dialog).getByRole("button", { name: "Add system" }));
  await userEvent.selectOptions(within(dialog).getByLabelText(/^System 1/), "gis");
  await userEvent.selectOptions(within(dialog).getByLabelText("Resource for system 1"), "bea");
  await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));

  expect(save).toHaveBeenCalledWith({
    id: "care-squad", name: "Care squad", value_stream_id: "retail", scrum_master_person_id: "sam",
    systems: [{ system_id: "gis", person_id: "bea" }], revision: 1,
  }, undefined);
  expect(await screen.findByText("Care squad saved.")).toBeVisible();
});

it("updates a squad against its revision", async () => {
  const save = vi.spyOn(organisationApi, "saveSquad").mockResolvedValue(organisation);

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: "Edit Sales squad" }));
  const dialog = await screen.findByRole("dialog");
  await userEvent.selectOptions(within(dialog).getByLabelText("Resource for system 2"), "layla");
  await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));

  expect(save).toHaveBeenCalledWith(expect.objectContaining({
    id: "sales",
    systems: [{ system_id: "bcrm", person_id: "bea" }, { system_id: "gis", person_id: "layla" }],
  }), 2);
});

it("lists people with the roles they hold", async () => {
  renderPage();

  await userEvent.click(await screen.findByRole("tab", { name: /People/ }));
  const table = screen.getByRole("table", { name: /People/ });
  expect(within(table).getByText("Leads Retail")).toBeVisible();
  expect(within(table).getByText("Scrum master of Sales squad")).toBeVisible();
  expect(within(table).getByText("Resource on 1 squad system")).toBeVisible();
});

it("lets readers look but not edit", async () => {
  vi.spyOn(knowledgeApi, "me").mockResolvedValue(reader as unknown as Actor);

  renderPage();

  expect(await screen.findByRole("article", { name: "Retail" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Add value stream" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Add squad" })).not.toBeInTheDocument();
});

it("makes readable, unique ids from names", () => {
  expect(newId("Care Squad", [])).toBe("care-squad");
  expect(newId("Care Squad", ["care-squad", "care-squad-2"])).toBe("care-squad-3");
  expect(newId("!!!", [])).toBe("item");
});

it("adds a person and a value stream led by them", async () => {
  const person = vi.spyOn(organisationApi, "savePerson").mockResolvedValue(organisation);
  const stream = vi.spyOn(organisationApi, "saveValueStream").mockResolvedValue(organisation);

  renderPage();

  await userEvent.click(await screen.findByRole("tab", { name: /People/ }));
  await userEvent.click(screen.getByRole("button", { name: "Add person" }));
  let dialog = await screen.findByRole("dialog");
  await userEvent.type(within(dialog).getByLabelText(/^Name/), "Nour Ops");
  await userEvent.type(within(dialog).getByLabelText(/^Team/), "Operations");
  await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
  expect(person).toHaveBeenCalledWith(
    { id: "nour-ops", name: "Nour Ops", team: "Operations", email: null, active: true, revision: 1 },
    undefined,
  );

  await userEvent.click(screen.getByRole("button", { name: "Add value stream" }));
  dialog = await screen.findByRole("dialog");
  await userEvent.type(within(dialog).getByLabelText(/Value stream name/), "Wholesale");
  await userEvent.selectOptions(within(dialog).getByLabelText(/Value stream lead/), "layla");
  await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
  expect(stream).toHaveBeenCalledWith(
    { id: "wholesale", name: "Wholesale", lead_person_id: "layla", revision: 1 }, undefined,
  );
});

it("links a product to systems and removes a squad after confirmation", async () => {
  const product = vi.spyOn(organisationApi, "saveProduct").mockResolvedValue(organisation);
  const removeSquad = vi.spyOn(organisationApi, "removeSquad").mockResolvedValue(organisation);

  renderPage();

  const stream = await screen.findByRole("article", { name: "Retail" });
  await userEvent.click(within(stream).getByRole("button", { name: "Add product" }));
  const dialog = await screen.findByRole("dialog");
  await userEvent.type(within(dialog).getByLabelText(/Product name/), "Fibre");
  await userEvent.type(within(dialog).getByLabelText("Filter systems"), "gi");
  await userEvent.click(within(dialog).getByLabelText("GIS"));
  await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
  expect(product).toHaveBeenCalledWith(expect.objectContaining({
    id: "fibre", value_stream_id: "retail", system_ids: ["gis"],
  }), undefined);

  await userEvent.click(within(stream).getByRole("button", { name: "Remove Sales squad" }));
  await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Remove" }));
  expect(removeSquad).toHaveBeenCalledWith("sales", 2);
});

it("asks for the reader role before showing anything", async () => {
  vi.spyOn(knowledgeApi, "me").mockResolvedValue({ ...maintainer, roles: [] } as unknown as Actor);
  const get = vi.spyOn(organisationApi, "get");

  renderPage();

  expect(await screen.findByText(/needs the knowledge reader role/)).toBeVisible();
  expect(get).not.toHaveBeenCalled();
});
