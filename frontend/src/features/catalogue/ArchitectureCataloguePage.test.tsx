import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import {
  knowledgeApi,
  type ArchitectureJob,
  type KnowledgeRelease,
  type MappingImpact,
  type Suggestion,
  type SuggestionsOverview,
} from "../../api/knowledge";
import { organisationApi, type Organisation } from "../../api/organisation";
import { renderWithClient } from "../../test/renderWithClient";
import { ArchitectureCataloguePage } from "./ArchitectureCataloguePage";

type Actor = Awaited<ReturnType<typeof knowledgeApi.me>>;

const maintainer = { id: "editor", display_name: "Kim Editor", roles: ["knowledge_maintainer"] };

const release = (changes: Partial<KnowledgeRelease> = {}): KnowledgeRelease => ({
  id: "draft-1",
  revision: 3,
  status: "draft",
  built_revision: null,
  published_at: null,
  published_by: null,
  index_profile: null,
  index_hash: null,
  systems: [
    { id: "bcrm", name: "BCRM", name_ar: null, aliases: ["CRM"],
      capabilities: [{ id: "order", name: "Ordering", triggers: ["order"] }], constraints: [] },
    { id: "billing", name: "Billing", name_ar: null, aliases: [], capabilities: [], constraints: [] },
  ],
  relationships: [{ source_system_id: "bcrm", target_system_id: "billing", description: "Bills orders", kind: "unspecified" }],
  documents: [{
    id: "doc-1", title: "Order design", filename: "design.docx", mime_type: "application/pdf",
    language: "en", checksum: "abc", uploaded_by: "editor", uploaded_at: "2026-09-29T09:00:00Z",
  }],
  ...changes,
});

const active = release({
  id: "published-1", status: "published", built_revision: 3, published_at: "2026-09-01T09:00:00Z",
  published_by: "amina",
});

const suggestion = (changes: Partial<Suggestion> = {}): Suggestion => ({
  id: "s-1",
  document_version_id: "doc-1",
  content: { kind: "system", system_id: "order-hub", name: "Order Hub", name_ar: null, aliases: ["OH"],
    capability_id: null, triggers: [], target_system_id: null, text: "" },
  citations: [{ location: "paragraph 2", quote: "The Order Hub captures orders" }],
  match: "new",
  status: "proposed",
  edited: false,
  model: "fake",
  prompt_version: "catalogue-extraction-v1",
  created_at: "2026-09-29T09:00:00Z",
  decided_by: null,
  decided_at: null,
  basis: "stated",
  rationale: null,
  possible_matches: [],
  system_name: null,
  target_system_name: null,
  ...changes,
});

const overview = (suggestions: Suggestion[]): SuggestionsOverview => ({
  release_id: "draft-1", release_revision: 3, suggestions,
  runs: [{ id: "run-1", document_version_id: "doc-1", model: "fake", prompt_version: "v1",
    candidate_count: suggestions.length, warnings: ["1 suggestion(s) already in the draft were left out."],
    created_at: "2026-09-29T09:00:00Z", match_model: null, match_prompt_version: null }],
});

const job = (
  status: ArchitectureJob["status"],
  kind: ArchitectureJob["kind"] = "extraction",
): ArchitectureJob => ({
  id: "job-1", kind, subject_id: "draft-1", fingerprint: kind === "index" ? "3|profile" : "doc-1|fake",
  actor_id: "editor",
  status, attempts: 1, error_category: status === "failed" ? "catalogue_extraction" : null,
});

const organisation: Organisation = {
  people: [],
  value_streams: [{ id: "vs", name: "Digital sales", lead_person_id: null, revision: 1 }],
  products: [{ id: "portal", name: "Partner portal", value_stream_id: "vs", description: "", system_ids: ["bcrm"],
    revision: 1 }],
  squads: [{ id: "orders", name: "Orders squad", value_stream_id: "vs", scrum_master_person_id: null,
    systems: [{ system_id: "bcrm", person_id: null }], revision: 1 }],
};

const impact = (changes: Partial<MappingImpact> = {}): MappingImpact => ({
  active_release_id: "published-1", requirements: 0, features: 0, stories: 0,
  outdated_requirements: 0, outdated_features: 0, outdated_stories: 0, ...changes,
});

const compared = (inUse: string[], thisVersion: string[]) => ({
  query: "q",
  in_use: { release_id: "published-1", systems: inUse.map((name) => ({ id: name.toLowerCase(), name })), uncertainty: null },
  this_version: { release_id: "draft-1", systems: thisVersion.map((name) => ({ id: name.toLowerCase(), name })),
    uncertainty: null },
});

function renderPage(url = "/architecture-knowledge") {
  return renderWithClient(<MemoryRouter initialEntries={[url]}><ArchitectureCataloguePage /></MemoryRouter>);
}

/** Opens the step the desk's NEXT block points at; the page lands on the systems. */
async function openNext() {
  await userEvent.click(await screen.findByRole("button", { name: /^Open (Add content|Review changes|Build evidence index|Publish)$/ }));
}

/** Switches the workbench to one of its views: Systems, Dependencies or History. */
async function openView(name: string) {
  await userEvent.click(within(await screen.findByRole("group", { name: "View" })).getByRole("button", { name }));
}

beforeEach(() => {
  vi.spyOn(knowledgeApi, "me").mockResolvedValue(maintainer as unknown as Actor);
  vi.spyOn(knowledgeApi, "active").mockResolvedValue(active);
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release(), active]);
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([]));
  vi.spyOn(knowledgeApi, "audit").mockResolvedValue([]);
  vi.spyOn(knowledgeApi, "extractions").mockResolvedValue([]);
  vi.spyOn(knowledgeApi, "buildStatus").mockResolvedValue(null);
  vi.spyOn(organisationApi, "get").mockResolvedValue(organisation);
  vi.spyOn(knowledgeApi, "samples").mockResolvedValue({ revision: 0, items: [], updated_by: null, updated_at: null });
  vi.spyOn(knowledgeApi, "mappingImpact").mockResolvedValue(impact());
  vi.spyOn(knowledgeApi, "changes").mockResolvedValue({
    base_release_id: "published-1", draft_release_id: "draft-1",
    changes: [{ item: "system", change: "added", key: "erp", label: "ERP", fields: [] }],
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

it("asks for maintainer access and never requests the catalogue without it", async () => {
  vi.spyOn(knowledgeApi, "me").mockResolvedValue({ ...maintainer, roles: [] } as unknown as Actor);
  const releases = vi.spyOn(knowledgeApi, "releases");

  renderPage();

  expect(await screen.findByText(/needs the knowledge maintainer role/)).toBeVisible();
  expect(releases).not.toHaveBeenCalled();
  expect(screen.getByRole("link", { name: "Squad catalogue" })).toHaveAttribute("href", "/architecture-knowledge/squads");
});

it("offers to start a new version when none is in progress", async () => {
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([active]);
  const create = vi.spyOn(knowledgeApi, "createDraft").mockResolvedValue(release());

  renderPage();

  expect(await screen.findByText("2 systems · 1 dependencies")).toBeVisible();
  const [start] = screen.getAllByRole("button", { name: "Start a new version" });
  if (!start) throw new Error("Expected a start button.");
  await userEvent.click(start);
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByRole("button", { name: "Start version" })).toBeDisabled();
  await userEvent.type(within(dialog).getByLabelText(/Version name/), "October integration update");
  await userEvent.click(within(dialog).getByRole("button", { name: "Start version" }));
  expect(create).toHaveBeenCalledWith("October integration update");
});

it("shows AI suggestions with their evidence and accepts one", async () => {
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([
    suggestion(),
    suggestion({ id: "s-2", match: "needs_system", content: { kind: "constraint", system_id: "order-hub", name: "",
      name_ar: null, aliases: [], capability_id: null, triggers: [], target_system_id: null, text: "Read-only at night" } }),
  ]));
  const decide = vi.spyOn(knowledgeApi, "decide").mockResolvedValue(release({ revision: 4 }));

  renderPage();
  await openNext();

  const systems = await screen.findByRole("region", { name: "Systems" });
  expect(within(systems).getByText("Order Hub")).toBeVisible();
  expect(within(systems).getByText("“The Order Hub captures orders”")).toBeVisible();
  expect(within(systems).getByText("Order design · paragraph 2")).toBeVisible();
  expect(screen.getByText("Needs its system first")).toBeVisible();
  expect(screen.getByText("1 suggestion(s) already in the draft were left out.")).toBeVisible();

  await userEvent.click(within(systems).getByRole("button", { name: "Accept Order Hub" }));

  expect(decide).toHaveBeenCalledWith(expect.objectContaining({ id: "draft-1", revision: 3 }), "s-1", true, undefined);
  expect(await screen.findByText("Added to this version.")).toBeVisible();
});

const dynamics = suggestion({
  id: "s-dyn",
  content: { kind: "system", system_id: "dynamics-crm", name: "Dynamics CRM", name_ar: null, aliases: [],
    capability_id: null, triggers: [], target_system_id: null, text: "" },
  citations: [{ location: "paragraph 4", quote: "Quotes are prepared in Dynamics CRM" }],
  possible_matches: [{ role: "system", written_as: "Dynamics CRM", system_id: "bcrm", system_name: "BCRM",
    reason: "Dynamics CRM is the sales CRM that BCRM is also called." }],
});

const inferred = suggestion({
  id: "s-inf",
  content: { kind: "relationship", system_id: "bcrm", name: "", name_ar: null, aliases: [], capability_id: null,
    triggers: [], target_system_id: "billing", text: "Sends invoices" },
  citations: [{ location: "paragraph 5", quote: "BCRM sends each invoice to Billing" }],
  basis: "inferred",
  rationale: "BCRM hands invoices to Billing, so it relies on Billing to receive them.",
  system_name: "BCRM",
  target_system_name: "Billing",
});

it("offers the existing system a name may be, and keeps it new only when asked", async () => {
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([dynamics]));
  const decide = vi.spyOn(knowledgeApi, "decide").mockResolvedValue(release({ revision: 4 }));

  renderPage();
  await openNext();

  const options = await screen.findByRole("group", { name: "Possible existing systems for “Dynamics CRM”" });
  expect(within(options).getByText(/Dynamics CRM is the sales CRM/)).toBeVisible();
  expect(screen.getByText("May already exist")).toBeVisible();
  // The existing system is shown by what it is, not only its name.
  expect(within(options).getByText(/Also called CRM · Ordering/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Accept Dynamics CRM" })).not.toBeInTheDocument();
  await userEvent.click(within(options).getByRole("button", { name: "Add to BCRM: “Dynamics CRM” as another name" }));
  expect(decide).toHaveBeenLastCalledWith(expect.anything(), "s-dyn", true,
    expect.objectContaining({ system_id: "bcrm", name: "Dynamics CRM" }));
  expect(await screen.findByText("“Dynamics CRM” added to BCRM as another name.")).toBeVisible();

  await userEvent.click(await screen.findByRole("button", { name: "Keep as a new system: “Dynamics CRM”" }));
  expect(decide).toHaveBeenLastCalledWith(expect.anything(), "s-dyn", true, undefined);
});

it("keeps a blocked dependency's state visible beside its possible match", async () => {
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([suggestion({
    id: "s-dep", match: "needs_system",
    content: { kind: "relationship", system_id: "order-hub", name: "", name_ar: null, aliases: [], capability_id: null,
      triggers: [], target_system_id: "dynamics-crm", text: "Quotes" },
    possible_matches: [{ role: "target", written_as: "Dynamics CRM", system_id: "bcrm", system_name: "BCRM",
      reason: "The sales CRM." }],
  })]));
  const decide = vi.spyOn(knowledgeApi, "decide").mockResolvedValue(release({ revision: 4 }));

  renderPage();
  await openNext();

  expect(await screen.findByText("May already exist")).toBeVisible();
  expect(screen.getByText("Needs its system first")).toBeVisible();
  expect(screen.getByRole("button", { name: /^Accept as written: / })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /^Use BCRM for “Dynamics CRM” in / }));
  expect(decide).toHaveBeenLastCalledWith(expect.anything(), "s-dep", true,
    expect.objectContaining({ system_id: "order-hub", target_system_id: "bcrm" }));
});

it("says which suggestions were read straight from a table", async () => {
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([
    suggestion({ id: "s-row", model: "catalogue-table-reader", prompt_version: "catalogue-tables-v1" }),
    dynamics,
  ]));

  renderPage();
  await openNext();

  expect(await screen.findAllByText("Read from table")).toHaveLength(1);
});

it("reads landscape suggestions in words and moves a placement before accepting it", async () => {
  const base = { name_ar: null, aliases: [], capability_id: null, triggers: [], target_system_id: null, text: "" };
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([
    suggestion({ id: "s-dom", content: { ...base, kind: "landscape_domain", system_id: "customer-assisted",
      name: "Assisted", landscape_domain_id: "customer-assisted", parent_domain_id: "customer" } }),
    suggestion({ id: "s-top", content: { ...base, kind: "landscape_domain", system_id: "customer",
      name: "Customer", landscape_domain_id: "customer", description: "TAM · Customer" } }),
    suggestion({ id: "s-place", content: { ...base, kind: "placement", system_id: "bcrm", name: "",
      landscape_domain_id: "customer-assisted" }, system_name: "BCRM" }),
  ]));
  const decide = vi.spyOn(knowledgeApi, "decide").mockResolvedValue(release({ revision: 4 }));

  renderPage();
  await openNext();

  expect(await screen.findByText("A sub-domain of Customer")).toBeVisible();
  expect(screen.getByText("A landscape domain · TAM · Customer")).toBeVisible();
  expect(screen.getByText("Place BCRM in Customer › Assisted")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Edit and accept Place BCRM in Customer › Assisted" }));
  const dialog = await screen.findByRole("dialog", { name: "Edit where the system sits before accepting" });
  await userEvent.selectOptions(within(dialog).getByLabelText(/^Landscape domain/), "Customer");
  await userEvent.click(within(dialog).getByRole("button", { name: "Accept with these edits" }));
  expect(decide).toHaveBeenLastCalledWith(expect.anything(), "s-place", true,
    expect.objectContaining({ kind: "placement", system_id: "bcrm", landscape_domain_id: "customer" }));
});

it("marks an inferred dependency with its reasoning and leaves it out of accept all", async () => {
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([suggestion(), inferred, dynamics]));
  const acceptAll = vi.spyOn(knowledgeApi, "acceptAll").mockResolvedValue({ accepted: 1, remaining: 2 } as never);

  renderPage();
  await openNext();

  expect(await screen.findByText("Inferred")).toBeVisible();
  expect(screen.getByText(/BCRM hands invoices to Billing/)).toBeVisible();
  expect(screen.getByText("Inferred, not stated.")).toBeVisible();
  expect(screen.getByText(/2 need a decision one by one/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Accept all 1 waiting" }));
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByText(/1 system\. 2 inferred or possibly existing items stay for you/)).toBeVisible();
  await userEvent.click(within(dialog).getByRole("button", { name: "Accept all" }));
  expect(acceptAll).toHaveBeenCalledOnce();
  expect(await screen.findByText(/2 still wait for a decision one by one/)).toBeVisible();
});

it("edits a suggestion before accepting it", async () => {
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([suggestion()]));
  const decide = vi.spyOn(knowledgeApi, "decide").mockResolvedValue(release({ revision: 4 }));

  renderPage();
  await openNext();

  await userEvent.click(await screen.findByRole("button", { name: "Edit and accept Order Hub" }));
  const dialog = await screen.findByRole("dialog");
  await userEvent.clear(within(dialog).getByLabelText("Other names"));
  await userEvent.type(within(dialog).getByLabelText("Other names"), "OH, Order hub platform");
  await userEvent.click(within(dialog).getByRole("button", { name: "Accept with these edits" }));

  expect(decide).toHaveBeenCalledWith(expect.anything(), "s-1", true,
    expect.objectContaining({ aliases: ["OH", "Order hub platform"], name: "Order Hub" }));
});

it("uploads a document and starts reading it for suggestions", async () => {
  const withSecond = release({ revision: 4, documents: [...release().documents, {
    id: "doc-2", title: "diagram", filename: "diagram.png", mime_type: "image/png", language: "en",
    checksum: "def", uploaded_by: "editor", uploaded_at: "2026-09-29T09:05:00Z" }] });
  const upload = vi.spyOn(knowledgeApi, "upload").mockResolvedValue(withSecond);
  const extract = vi.spyOn(knowledgeApi, "extract").mockResolvedValue(job("succeeded"));
  vi.spyOn(knowledgeApi, "job").mockResolvedValue(job("succeeded"));

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  const input = screen.getByLabelText("Add documents", { selector: "input" });
  await userEvent.upload(input, new File(["png"], "diagram.png", { type: "image/png" }));

  expect(upload).toHaveBeenCalledWith(expect.objectContaining({ id: "draft-1" }), expect.any(File), "diagram", "en");
  expect(extract).toHaveBeenCalledWith(withSecond, "doc-2");
  expect(await screen.findByText(/1 document added/)).toBeVisible();
});

it("uploads a spreadsheet with the type the server expects", async () => {
  const upload = vi.spyOn(knowledgeApi, "upload").mockResolvedValue(release({ revision: 4 }));
  vi.spyOn(knowledgeApi, "extract").mockResolvedValue(job("succeeded"));
  vi.spyOn(knowledgeApi, "job").mockResolvedValue(job("succeeded"));

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  const input = screen.getByLabelText("Add documents", { selector: "input" });
  expect(input).toHaveAttribute("accept", expect.stringContaining(".xlsx"));
  await userEvent.upload(input, new File(["csv"], "inventory.csv", { type: "application/vnd.ms-excel" }));

  expect(upload).toHaveBeenCalledWith(expect.anything(),
    expect.objectContaining({ name: "inventory.csv", type: "text/csv" }), "inventory", "en");
});

it("uploads a Markdown file the browser left untyped as Markdown", async () => {
  const upload = vi.spyOn(knowledgeApi, "upload").mockResolvedValue(release({ revision: 4 }));
  vi.spyOn(knowledgeApi, "extract").mockResolvedValue(job("succeeded"));
  vi.spyOn(knowledgeApi, "job").mockResolvedValue(job("succeeded"));

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  const input = screen.getByLabelText("Add documents", { selector: "input" });
  expect(input).toHaveAttribute("accept", expect.stringContaining(".md"));
  await userEvent.upload(input, new File(["# Systems"], "landscape.md", { type: "" }));

  expect(upload).toHaveBeenCalledWith(expect.anything(),
    expect.objectContaining({ name: "landscape.md", type: "text/markdown" }), "landscape", "en");
});

it("previews a catalogue file before replacing the draft with it", async () => {
  const preview = vi.spyOn(knowledgeApi, "previewFile").mockResolvedValue({
    base_release_id: "draft-1", draft_release_id: "draft-1",
    changes: [{ item: "system", change: "added", key: "erp", label: "ERP", fields: [] },
      { item: "system", change: "changed", key: "bcrm", label: "BCRM", fields: ["aliases"] }],
  });
  const apply = vi.spyOn(knowledgeApi, "importFile").mockResolvedValue(release({ revision: 4 }));

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  await userEvent.click(screen.getByRole("tab", { name: /Upload catalogue file/ }));
  const file = new File(["x"], "catalogue.xlsx");
  await userEvent.upload(screen.getByLabelText("Choose a catalogue file", { selector: "input" }), file);

  expect(preview).toHaveBeenCalledWith(expect.objectContaining({ id: "draft-1" }), file);
  expect(await screen.findByText("ERP")).toBeVisible();
  expect(screen.getByText("(other names)")).toBeVisible();
  expect(apply).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Replace this version’s content with the file" }));
  expect(apply).toHaveBeenCalledWith(expect.objectContaining({ id: "draft-1" }), file);
});

it("gates publishing on a built index and a rationale, then confirms", async () => {
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release({ built_revision: 3 }), active]);
  const publish = vi.spyOn(knowledgeApi, "publish").mockResolvedValue(active);

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 4: Publish/ }));
  const button = screen.getByRole("button", { name: "Publish this version" });
  expect(button).toHaveAttribute("aria-disabled", "true");
  expect(screen.getByText("Say what you checked before publishing.")).toBeVisible();

  await userEvent.type(screen.getByLabelText(/What did you check/), "Checked against the integration map");
  await userEvent.click(screen.getByRole("button", { name: "Publish this version" }));
  await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Publish" }));

  expect(publish.mock.calls[0]?.[0]).toMatchObject({ rationale: "Checked against the integration map" });
  expect(await screen.findByText("Published. Requirement mapping now uses this version.")).toBeVisible();
});

it("records how one system depends on another, when adding and on an existing dependency", async () => {
  const save = vi.spyOn(knowledgeApi, "save").mockResolvedValue(release({ revision: 4 }));

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  await userEvent.click(screen.getByRole("tab", { name: /Edit manually/ }));
  const dependencies = screen.getByRole("heading", { name: /Dependencies \(1\)/ }).parentElement;
  if (!dependencies) throw new Error("Expected the dependencies section.");

  const existing = within(dependencies).getByRole("combobox", { name: "How BCRM depends on Billing" });
  expect(existing).toHaveValue("unspecified");
  await userEvent.selectOptions(existing, "Sends it data");
  expect(save.mock.calls[0]?.[0].relationships).toEqual([
    { source_system_id: "bcrm", target_system_id: "billing", description: "Bills orders", kind: "transfers_data_to" },
  ]);

  await userEvent.selectOptions(within(dependencies).getByLabelText(/From system/), "Billing");
  await userEvent.selectOptions(within(dependencies).getByLabelText(/^Depends on/), "BCRM");
  await userEvent.type(within(dependencies).getByLabelText(/For what/), "Reads accounts");
  await userEvent.selectOptions(within(dependencies).getByLabelText("How"), "Calls its API");
  await userEvent.click(within(dependencies).getByRole("button", { name: "Add dependency" }));
  expect(save.mock.calls[1]?.[0].relationships.at(-1)).toEqual({
    source_system_id: "billing", target_system_id: "bcrm", description: "Reads accounts", kind: "calls_api",
  });
  await waitFor(() => expect(within(dependencies).getByLabelText(/For what/)).toHaveValue(""));
  expect(within(dependencies).getByLabelText("How")).toHaveValue("unspecified");
});

it("keeps a new dependency's input when saving it fails", async () => {
  vi.spyOn(knowledgeApi, "save").mockRejectedValue(new Error("The draft changed; reload before saving."));

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  await userEvent.click(screen.getByRole("tab", { name: /Edit manually/ }));
  const dependencies = screen.getByRole("heading", { name: /Dependencies \(1\)/ }).parentElement;
  if (!dependencies) throw new Error("Expected the dependencies section.");

  await userEvent.selectOptions(within(dependencies).getByLabelText(/From system/), "Billing");
  await userEvent.selectOptions(within(dependencies).getByLabelText(/^Depends on/), "BCRM");
  await userEvent.type(within(dependencies).getByLabelText(/For what/), "Reads accounts");
  await userEvent.selectOptions(within(dependencies).getByLabelText("How"), "Calls its API");
  await userEvent.click(within(dependencies).getByRole("button", { name: "Add dependency" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("draft changed");
  expect(within(dependencies).getByLabelText(/For what/)).toHaveValue("Reads accounts");
  expect(within(dependencies).getByLabelText("How")).toHaveValue("calls_api");
});

it("names a changed dependency kind in the review of changes", async () => {
  vi.spyOn(knowledgeApi, "changes").mockResolvedValue({
    base_release_id: "published-1", draft_release_id: "draft-1",
    changes: [{ item: "relationship", change: "changed", key: "bcrm->billing:bills orders",
      label: "BCRM → Billing: Bills orders", fields: ["kind"] }],
  });

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 2: Review changes/ }));
  expect(await screen.findByText(/1 dependency changed/)).toBeVisible();
  expect(screen.getByText("(how it depends)")).toBeVisible();
});

it("keeps capability domains: adds one, places a capability in it, and will not remove one in use", async () => {
  const save = vi.spyOn(knowledgeApi, "save").mockResolvedValue(release({ revision: 4 }));
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release({
    capability_domains: [{ id: "orders", name: "Order capture", name_ar: null, parent_id: null, description: null }],
    systems: [
      { id: "bcrm", name: "BCRM", name_ar: null, aliases: ["CRM"], constraints: [],
        capabilities: [{ id: "order", name: "Ordering", triggers: ["order"], domain_id: "orders" }] },
      { id: "billing", name: "Billing", name_ar: null, aliases: [], constraints: [],
        capabilities: [{ id: "bill", name: "Billing", triggers: ["bill"], domain_id: null }] },
    ],
  }), active]);

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  await userEvent.click(screen.getByRole("tab", { name: /Edit manually/ }));
  const domains = screen.getByRole("heading", { name: "Capability domains (1)" }).closest("section");
  if (!domains) throw new Error("Expected the domains section.");
  expect(within(domains).getByText("1 capability is not placed yet.", { exact: false })).toBeVisible();
  const remove = within(domains).getByRole("button", { name: "Remove Order capture" });
  expect(remove).toHaveAttribute("aria-disabled", "true");
  expect(remove).toHaveAccessibleDescription("Holds 1 capability from BCRM. Move them to remove this domain.");
  await userEvent.click(remove);
  expect(save).not.toHaveBeenCalled();

  await userEvent.click(within(domains).getByRole("button", { name: "Add domain" }));
  const dialog = await screen.findByRole("dialog");
  await userEvent.type(within(dialog).getByLabelText(/^Name/), "Quoting");
  await userEvent.selectOptions(within(dialog).getByLabelText(/Parent domain/), "Order capture");
  await userEvent.click(within(dialog).getByRole("button", { name: "Save domain" }));
  expect(save.mock.calls[0]?.[0].capability_domains?.at(-1)).toEqual({
    id: "quoting", name: "Quoting", name_ar: null, parent_id: "orders", description: null,
  });

  await userEvent.click(screen.getByRole("button", { name: "Billing" }));
  const system = await screen.findByRole("dialog");
  // Capabilities open folded to a summary that says where each one is placed.
  const card = within(system).getByRole("button", { name: /Capability 1:/ });
  expect(card).toHaveAttribute("aria-expanded", "false");
  expect(card).toHaveTextContent("No domain");
  await userEvent.click(card);
  await userEvent.selectOptions(within(system).getByLabelText(/Capability 1 domain/i), "Order capture");
  expect(card).toHaveTextContent("Order capture");
  await userEvent.click(within(system).getByRole("button", { name: "Save system" }));
  expect(save.mock.calls[1]?.[0].systems.find((item) => item.id === "billing")?.capabilities).toEqual([
    { id: "bill", name: "Billing", triggers: ["bill"], domain_id: "orders", component_id: null },
  ]);
});

it("reads the landscape by capability domain, with what nobody has placed yet", async () => {
  vi.spyOn(knowledgeApi, "active").mockResolvedValue({
    ...active,
    capability_domains: [
      { id: "orders", name: "Order capture", name_ar: null, parent_id: null, description: "Taking orders." },
    ],
    systems: [
      { id: "bcrm", name: "BCRM", name_ar: null, aliases: [], constraints: [],
        capabilities: [{ id: "order", name: "Ordering", triggers: ["order"], domain_id: "orders" }] },
      { id: "billing", name: "Billing", name_ar: null, aliases: [], constraints: [],
        capabilities: [{ id: "bill", name: "Invoicing", triggers: ["bill"], domain_id: null }] },
    ],
  });

  renderPage("/architecture-knowledge?version=in-use&view=domains");

  const tree = await screen.findByRole("region", { name: "Capability domains (1)" });
  expect(within(tree).getByRole("heading", { name: "Capability domains (1)", level: 2 })).toBeVisible();
  expect(within(tree).getByRole("heading", { name: "Order capture", level: 3 })).toBeVisible();
  expect(within(tree).getByText("1 capability · 1 system")).toBeVisible();
  expect(within(tree).getByText("Ordering")).toBeVisible();
  expect(within(tree).getByRole("heading", { name: "Not placed in a domain yet (1)" })).toBeVisible();
  await userEvent.click(within(tree).getByRole("button", { name: "Billing" }));
  expect(await screen.findByRole("heading", { name: "Billing", level: 3 })).toBeVisible();
});

it("keeps landscape domains apart: adds a sub-domain, places a system and says what it is for", async () => {
  const save = vi.spyOn(knowledgeApi, "save").mockResolvedValue(release({ revision: 4 }));
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release({
    landscape_domains: [{ id: "customer", name: "Customer", name_ar: null, parent_id: null, description: null }],
    systems: [
      { id: "bcrm", name: "BCRM", name_ar: null, aliases: [], constraints: [], capabilities: [],
        landscape_domain_id: "customer" },
      { id: "billing", name: "Billing", name_ar: null, aliases: [], constraints: [], capabilities: [] },
    ],
  }), active]);

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  await userEvent.click(screen.getByRole("tab", { name: /Edit manually/ }));
  const landscape = screen.getByRole("heading", { name: "Landscape domains (1)" }).closest("section");
  if (!landscape) throw new Error("Expected the landscape section.");
  expect(within(landscape).getByText("1 system is not placed yet.", { exact: false })).toBeVisible();
  expect(within(landscape).getByRole("button", { name: "Remove Customer" }))
    .toHaveAccessibleDescription("Holds system BCRM. Move them to remove this domain.");

  await userEvent.click(within(landscape).getByRole("button", { name: "Add landscape domain" }));
  const dialog = await screen.findByRole("dialog");
  await userEvent.type(within(dialog).getByLabelText(/^Name/), "Assisted");
  await userEvent.selectOptions(within(dialog).getByLabelText(/Parent domain/), "Customer");
  await userEvent.click(within(dialog).getByRole("button", { name: "Save domain" }));
  // A sub-domain's key says where it sits, and capability domains are left as they are.
  expect(save.mock.calls[0]?.[0].landscape_domains?.at(-1)).toEqual({
    id: "customer-assisted", name: "Assisted", name_ar: null, parent_id: "customer", description: null,
  });

  await userEvent.click(screen.getByRole("button", { name: "Billing" }));
  const system = await screen.findByRole("dialog");
  await userEvent.type(within(system).getByLabelText(/^Description/), "Bills customers.");
  await userEvent.selectOptions(within(system).getByLabelText(/^Landscape domain/), "Customer");
  await userEvent.click(within(system).getByRole("button", { name: "Save system" }));
  expect(save.mock.calls[1]?.[0].systems.find((item) => item.id === "billing")).toMatchObject({
    description: "Bills customers.", landscape_domain_id: "customer",
  });
});

it("reads where the systems sit before what they do, and opens a system from either", async () => {
  vi.spyOn(knowledgeApi, "active").mockResolvedValue({
    ...active,
    landscape_domains: [
      { id: "customer", name: "Customer", name_ar: null, parent_id: null, description: "TAM · Customer" },
      { id: "customer-assisted", name: "Assisted", name_ar: null, parent_id: "customer", description: null },
    ],
    systems: [
      { id: "cim", name: "CIM", name_ar: null, aliases: [], constraints: [], capabilities: [],
        description: "Agent screen for care.", landscape_domain_id: "customer-assisted" },
      { id: "billing", name: "Billing", name_ar: null, aliases: [], constraints: [], capabilities: [] },
    ],
  });

  renderPage("/architecture-knowledge?version=in-use&view=domains");

  const tree = await screen.findByRole("region", { name: "Landscape domains (2)" });
  expect(within(tree).getByRole("heading", { name: "Customer", level: 3 })).toBeVisible();
  expect(within(tree).getByRole("heading", { name: "Assisted", level: 4 })).toBeVisible();
  expect(within(tree).getByText("Agent screen for care.")).toBeVisible();
  expect(within(tree).getByRole("heading", { name: "Not placed in the landscape yet (1)" })).toBeVisible();
  await userEvent.click(within(tree).getByRole("button", { name: "CIM" }));
  const dossier = await screen.findByRole("article", { name: "CIM" });
  expect(within(dossier).getByText("Landscape: Customer › Assisted")).toBeVisible();
  expect(within(dossier).getByText("Agent screen for care.")).toBeVisible();
});

const officeConnect = {
  id: "office-connect", name: "Office Connect", code: "OFFICE_CONNECT", family: "Connect", version: "1.0.0",
  lifecycle: "REFERENCE", proposition: "A fixed connection with a managed router.", rules: ["The router is mandatory."],
  order_types: [
    { code: "NEW_ACTIVATION", name: "New Activation", enabled: true },
    { code: "UPGRADE", name: "Upgrade", enabled: false, confidence: "gap" as const },
  ],
  components: [{
    id: "fibre", name: "Fibre Access", kind: "SERVICE", mandatory: true, customer_visible: true,
    description: "Primary fixed connection.", confidence: "confirmed" as const,
    responsibilities: [
      { system_id: "bcrm", role: "CUSTOMER_CONTEXT", description: "Supplies the account.", order_types: ["NEW_ACTIVATION"] },
      { system_id: "billing", role: "BILLING", description: "Bills the line.", order_types: [], confidence: "inferred" as const },
    ],
  }],
  values: [{ name: "Secure connectivity", description: "Firewall included." }],
  audiences: [{ name: "Branch offices" }],
};

it("shows what each product offering is made of and which system does what", async () => {
  vi.spyOn(knowledgeApi, "active").mockResolvedValue({ ...active, products: [officeConnect] });

  renderPage("/architecture-knowledge?version=in-use&view=products");

  const offering = await screen.findByRole("article", { name: /Office Connect/ });
  expect(within(offering).getByText("Connect family · version 1.0.0 · Reference", { exact: false })).toBeVisible();
  expect(within(offering).getByText("Not offered yet")).toBeVisible();
  expect(within(offering).getByText("Known gap")).toBeVisible();
  const components = within(offering).getByRole("table", { name: "Components of Office Connect" });
  expect(within(components).getByRole("cell", { name: "Service" })).toBeVisible();
  const matrix = within(offering).getByRole("table", { name: "Which system does what for Office Connect" });
  expect(within(matrix).getByRole("columnheader", { name: "BCRM" })).toBeVisible();
  expect(within(matrix).getByRole("rowheader", { name: "Fibre Access" })).toBeVisible();
  expect(within(matrix).getByRole("cell", { name: "Customer context" })).toBeVisible();
  expect(within(offering).getByText(/Supplies the account\. For New Activation\./)).toBeVisible();
  expect(within(offering).getByText("Branch offices")).toBeVisible();
  await userEvent.click(within(offering).getByRole("button", { name: "Billing" }));
  expect(await screen.findByRole("heading", { name: "Billing", level: 3 })).toBeVisible();
});

it("adds a product offering by hand with a component and the system that delivers it", async () => {
  const save = vi.spyOn(knowledgeApi, "save").mockResolvedValue(release({ revision: 4 }));
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release({ products: [officeConnect] }), active]);

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  await userEvent.click(screen.getByRole("tab", { name: /Edit manually/ }));
  const section = screen.getByRole("heading", { name: "Product offerings (1)" }).closest("section");
  if (!section) throw new Error("Expected the offerings section.");
  expect(within(section).getByText("2 order types · 1 component · 2 system responsibilities")).toBeVisible();

  await userEvent.click(within(section).getByRole("button", { name: "Add product offering" }));
  const drawer = await screen.findByRole("dialog", { name: "Add a product offering" });
  // Saving an empty component says what is missing, beside the field.
  await userEvent.type(within(drawer).getByLabelText(/^Name/), "Office Secure");
  await userEvent.click(within(drawer).getByRole("button", { name: "Add order type" }));
  await userEvent.type(within(drawer).getByLabelText(/^Order type 1, name/), "New Activation");
  await userEvent.type(within(drawer).getByLabelText(/Order type 1 Code/), "NEW_ACTIVATION");
  await userEvent.click(within(drawer).getByRole("button", { name: "Add component" }));
  await userEvent.click(within(drawer).getByRole("button", { name: "Add a system to Component 1" }));
  await userEvent.click(within(drawer).getByRole("button", { name: "Save offering" }));
  expect(within(drawer).getByText("Give the component a name.")).toBeVisible();
  expect(save).not.toHaveBeenCalled();

  await userEvent.type(within(drawer).getByLabelText(/^Name of component 1/), "Firewall");
  await userEvent.selectOptions(within(drawer).getByLabelText(/responsibility 1: System/), "BCRM");
  await userEvent.type(within(drawer).getByLabelText(/responsibility 1: Role/), "Customer context");
  await userEvent.type(within(drawer).getByLabelText(/responsibility 1: What it does/), "Supplies the account.");
  await userEvent.click(within(drawer).getByRole("checkbox", { name: "New Activation" }));
  await userEvent.click(within(drawer).getByRole("button", { name: "Save offering" }));

  const saved = save.mock.calls[0]?.[0].products?.at(-1);
  expect(saved).toMatchObject({
    id: "office-secure", name: "Office Secure",
    order_types: [{ code: "NEW_ACTIVATION", name: "New Activation", enabled: true }],
    components: [{ id: "firewall", name: "Firewall", responsibilities: [
      { system_id: "bcrm", role: "Customer context", description: "Supplies the account.", order_types: ["NEW_ACTIVATION"] },
    ] }],
  });
  expect(save.mock.calls[0]?.[0].products?.[0]).toEqual(officeConnect);
});

it("suggests a whole product offering and corrects it in the offering drawer before accepting", async () => {
  const base = { name_ar: null, aliases: [], capability_id: null, triggers: [], target_system_id: null, text: "" };
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([
    suggestion({ id: "s-offer", match: "needs_system",
      content: { ...base, kind: "product", system_id: "office-connect", name: "Office Connect", product: officeConnect } }),
  ]));
  const decide = vi.spyOn(knowledgeApi, "decide").mockResolvedValue(release({ revision: 4 }));

  renderPage();
  await openNext();

  expect(await screen.findByText("Product offering: Office Connect")).toBeVisible();
  expect(screen.getByText("2 order types · 1 component · 2 system responsibilities")).toBeVisible();
  expect(screen.getByText("Needs its system first")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Edit and accept Product offering: Office Connect" }));
  const drawer = await screen.findByRole("dialog", { name: "Edit the product offering before accepting" });
  const version = within(drawer).getByLabelText(/^Version/);
  await userEvent.clear(version);
  await userEvent.type(version, "1.1.0");
  await userEvent.click(within(drawer).getByRole("button", { name: "Accept with these edits" }));
  expect(decide).toHaveBeenLastCalledWith(expect.anything(), "s-offer", true, expect.objectContaining({
    kind: "product", system_id: "office-connect",
    product: expect.objectContaining({ id: "office-connect", version: "1.1.0" }),
  }));
});

const activation = {
  id: "new-activation", name: "New Activation", product_id: "office-connect", order_type_code: "NEW_ACTIVATION",
  activities: [
    { number: "10", name: "Select offer", performing_system_id: "bcrm", supporting_system_ids: ["billing"],
      system_function: "Offer UI and basket", customer_visible: true, component_ids: [] },
    { number: "20", name: "Validate order", performing_system_id: "bcrm", phase: "VALIDATION",
      supporting_system_ids: [], component_ids: [] },
    { number: "25", name: "Correct order", track: "CORRECTION", performing_system_id: "billing",
      confidence: "inferred" as const, supporting_system_ids: [], component_ids: [] },
    { number: "30", name: "Bill", performing_system_id: "billing", supporting_system_ids: [], component_ids: [] },
  ],
  flow_rules: [
    { kind: "decision" as const, from_activity: "20", to_activity: "30", condition: "PASS" },
    { kind: "decision" as const, from_activity: "20", to_activity: "25", condition: "FAIL" },
    { kind: "loop" as const, from_activity: "25", to_activity: "10", condition: "Resubmit" },
  ],
  integrations: [{ from_activity: "10", to_activity: "20", interaction: "API", payload: "Basket", timing: "SYNC" }],
  edges: [
    { from_activity: "10", to_activity: "20", kind: "sequence", label: null },
    { from_activity: "20", to_activity: "30", kind: "decision", label: "PASS" },
    { from_activity: "20", to_activity: "25", kind: "decision", label: "FAIL" },
    { from_activity: "25", to_activity: "10", kind: "loop", label: "Resubmit" },
  ],
};

it("walks a journey's activities in order and draws its flow from the server's edges", async () => {
  vi.spyOn(knowledgeApi, "active").mockResolvedValue({ ...active, products: [officeConnect], journeys: [activation] });

  renderPage("/architecture-knowledge?version=in-use&view=journeys");

  const journey = await screen.findByRole("article", { name: /New Activation/ });
  expect(within(journey).getByText("Office Connect › New Activation", { exact: false })).toBeVisible();
  const table = within(journey).getByRole("table", { name: "Activities of New Activation, in order" });
  const rows = within(table).getAllByRole("row").slice(1);
  expect(rows.map((row) => within(row).getAllByRole("cell")[0]?.textContent)).toEqual([
    expect.stringContaining("10. Select offer"), expect.stringContaining("20. Validate order"),
    expect.stringContaining("25. Correct order"), expect.stringContaining("30. Bill"),
  ]);
  expect(within(rows[2]!).getByRole("cell", { name: "Correction track" })).toBeVisible();
  expect(within(table).getByText("Customer sees it")).toBeVisible();
  const flow = within(journey).getByRole("region", { name: "Flow of New Activation" });
  expect(within(flow).getByRole("img", { name: /4 activities and 4 arrows/ })).toBeInTheDocument();
  expect(within(flow).getByText("FAIL")).toBeInTheDocument();
  expect(within(journey).getByText(/From 20\. Validate order to 25\. Correct order when FAIL/)).toBeVisible();
  expect(within(journey).getByRole("table", { name: "How the activities of New Activation hand over" })).toBeVisible();
  await userEvent.click(within(rows[0]!).getByRole("button", { name: "Billing" }));
  expect(await screen.findByRole("heading", { name: "Billing", level: 3 })).toBeVisible();
});

it("adds a journey by hand: its offering, activities in order and a decision", async () => {
  const save = vi.spyOn(knowledgeApi, "save").mockResolvedValue(release({ revision: 4 }));
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release({ products: [officeConnect] }), active]);

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  await userEvent.click(screen.getByRole("tab", { name: /Edit manually/ }));
  await userEvent.click(screen.getByRole("button", { name: "Add journey" }));
  const drawer = await screen.findByRole("dialog", { name: "Add a journey" });
  await userEvent.type(within(drawer).getByLabelText(/^Name/), "New Activation");
  await userEvent.selectOptions(within(drawer).getByLabelText(/^Product offering/), "Office Connect");
  await userEvent.selectOptions(within(drawer).getByLabelText(/^Order type/), "New Activation");
  for (const [number, name] of [["10", "Select offer"], ["20", "Validate"], ["10", "Again"]]) {
    await userEvent.click(within(drawer).getByRole("button", { name: "Add activity" }));
    const position = within(drawer).getAllByLabelText(/^Activity \d+: Number/).length;
    await userEvent.type(within(drawer).getByLabelText(new RegExp(`^Activity ${position}: Number`)), number!);
    await userEvent.type(within(drawer).getByLabelText(new RegExp(`^Activity ${position}: Name`)), name!);
  }
  await userEvent.selectOptions(within(drawer).getByLabelText(/^Activity 1: Performed by/), "BCRM");
  await userEvent.click(within(drawer).getByRole("button", { name: "Save journey" }));
  expect(within(drawer).getByText("Another activity has this number.")).toBeVisible();
  expect(save).not.toHaveBeenCalled();

  await userEvent.click(within(drawer).getByRole("button", { name: "Remove 10. Again" }));
  await userEvent.click(within(drawer).getByRole("button", { name: "Add rule" }));
  await userEvent.selectOptions(within(drawer).getByLabelText(/^Rule 1: From/), "10. Select offer");
  await userEvent.selectOptions(within(drawer).getByLabelText(/^Rule 1: To/), "20. Validate");
  await userEvent.type(within(drawer).getByLabelText(/^Rule 1: When/), "PASS");
  await userEvent.click(within(drawer).getByRole("button", { name: "Save journey" }));

  expect(save.mock.calls[0]?.[0].journeys?.at(-1)).toMatchObject({
    id: "new-activation", name: "New Activation", product_id: "office-connect", order_type_code: "NEW_ACTIVATION",
    activities: [
      { number: "10", name: "Select offer", performing_system_id: "bcrm" },
      { number: "20", name: "Validate" },
    ],
    flow_rules: [{ kind: "decision", from_activity: "10", to_activity: "20", condition: "PASS" }],
  });
  // Typing a journey's activities takes longer than the default five seconds.
}, 20_000);

it("suggests a whole journey and corrects it in the journey drawer before accepting", async () => {
  const base = { name_ar: null, aliases: [], capability_id: null, triggers: [], target_system_id: null, text: "" };
  // Its offering is itself still a suggestion, and one activity names a system this version lacks.
  const suggested = {
    ...activation,
    activities: [...activation.activities.slice(0, 3), { ...activation.activities[3]!, performing_system_id: "rule-desk" }],
  };
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([
    suggestion({ id: "s-offer", match: "needs_system",
      content: { ...base, kind: "product", system_id: "office-connect", name: "Office Connect", product: officeConnect } }),
    suggestion({ id: "s-journey", match: "needs_offering",
      content: { ...base, kind: "journey", system_id: "new-activation", name: "New Activation", journey: suggested } }),
  ]));
  const decide = vi.spyOn(knowledgeApi, "decide").mockResolvedValue(release({ revision: 4 }));

  renderPage();
  await openNext();

  expect(await screen.findByText("Journey: New Activation")).toBeVisible();
  expect(screen.getByText("For Office Connect › New Activation · 4 activities · 3 flow rules · 1 integration"))
    .toBeVisible();
  expect(screen.getByText("Needs its product offering first")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Edit and accept Journey: New Activation" }));
  const drawer = await screen.findByRole("dialog", { name: "Edit the journey before accepting" });
  expect(within(drawer).getByLabelText(/^Product offering/)).toHaveDisplayValue("Office Connect");
  await userEvent.click(within(drawer).getByRole("button", { name: /^30\. Bill/ }));
  expect(within(drawer).getByLabelText(/^Activity 4: Performed by/)).toHaveDisplayValue("rule-desk (not in this version)");
  await userEvent.type(within(drawer).getByLabelText(/^Description/), "Activates a new office line.");
  await userEvent.click(within(drawer).getByRole("button", { name: "Accept with these edits" }));

  expect(decide).toHaveBeenLastCalledWith(expect.anything(), "s-journey", true, expect.objectContaining({
    kind: "journey", system_id: "new-activation",
    journey: expect.objectContaining({
      product_id: "office-connect", order_type_code: "NEW_ACTIVATION", description: "Activates a new office line.",
      activities: expect.arrayContaining([expect.objectContaining({ number: "30", performing_system_id: "rule-desk" })]),
    }),
  }));
});

it("removes a product offering only after confirming", async () => {
  const save = vi.spyOn(knowledgeApi, "save").mockResolvedValue(release({ revision: 4 }));
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release({ products: [officeConnect] }), active]);

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  await userEvent.click(screen.getByRole("tab", { name: /Edit manually/ }));
  await userEvent.click(screen.getByRole("button", { name: "Remove Office Connect" }));
  const dialog = await screen.findByRole("dialog", { name: "Remove Office Connect?" });
  expect(save).not.toHaveBeenCalled();
  await userEvent.click(within(dialog).getByRole("button", { name: "Remove offering" }));
  expect(save.mock.calls[0]?.[0].products).toEqual([]);
});

it("shows the changes compared with the version in use", async () => {
  vi.spyOn(knowledgeApi, "changes").mockResolvedValue({
    base_release_id: "published-1", draft_release_id: "draft-1",
    changes: [{ item: "relationship", change: "removed", key: "a", label: "BCRM → Billing: Bills orders", fields: [] }],
  });

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 2: Review changes/ }));
  expect(await screen.findByText("BCRM → Billing: Bills orders")).toBeVisible();
  expect(screen.getByText("Removed")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "These changes are right — continue" }));
  expect(screen.getByRole("button", { name: /Step 3: Build evidence index/, current: "step" })).toBeVisible();
});

it("builds the index only when asked, and reports a failure in words", async () => {
  const build = vi.spyOn(knowledgeApi, "build").mockResolvedValue(job("failed", "index"));
  vi.spyOn(knowledgeApi, "buildStatus")
    .mockResolvedValueOnce(null)
    .mockResolvedValue(job("failed", "index"));
  vi.spyOn(knowledgeApi, "job").mockResolvedValue(job("failed", "index"));
  const retry = vi.spyOn(knowledgeApi, "retryJob").mockResolvedValue(job("queued", "index"));

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 3: Build evidence index/ }));
  // Opening the step only says where the index stands.
  expect(await screen.findByText(/Not built for the latest changes/)).toBeVisible();
  expect(build).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Build evidence index" }));
  expect(await screen.findByText("Failed")).toBeVisible();
  expect(build).toHaveBeenCalledOnce();
  expect(screen.getByText("Reason: no part of the document could be read by the AI model")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(retry).toHaveBeenCalledOnce();
});

it("adds a system by hand and removes a dependency", async () => {
  const save = vi.spyOn(knowledgeApi, "save").mockResolvedValue(release({ revision: 4 }));

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  await userEvent.click(screen.getByRole("tab", { name: /Edit manually/ }));
  await userEvent.click(screen.getByRole("button", { name: "Add system" }));
  const dialog = await screen.findByRole("dialog");
  // The ID follows the name until someone types their own.
  await userEvent.type(within(dialog).getByLabelText(/^Name/), "Finance ERP");
  expect(within(dialog).getByLabelText(/System ID/)).toHaveValue("finance-erp");
  await userEvent.clear(within(dialog).getByLabelText(/System ID/));
  await userEvent.type(within(dialog).getByLabelText(/System ID/), "erp");
  await userEvent.clear(within(dialog).getByLabelText(/^Name/));
  await userEvent.type(within(dialog).getByLabelText(/^Name/), "ERP");
  expect(within(dialog).getByLabelText(/System ID/)).toHaveValue("erp");
  // Other names are chips: Enter commits one, and text still in the field is kept on save.
  await userEvent.type(within(dialog).getByLabelText("Other names"), "Finance{enter}Ledger");
  expect(within(dialog).getByRole("button", { name: "Remove Finance" })).toBeVisible();
  await userEvent.click(within(dialog).getByRole("button", { name: "Add capability" }));
  expect(within(dialog).getByLabelText(/Capability 1 name/i)).toHaveFocus();
  await userEvent.type(within(dialog).getByLabelText(/Capability 1 name/i), "Posting");
  expect(within(dialog).getByLabelText(/Capability 1 ID/i)).toHaveValue("posting");
  await userEvent.clear(within(dialog).getByLabelText(/Capability 1 ID/i));
  await userEvent.type(within(dialog).getByLabelText(/Capability 1 ID/i), "post");
  // With no domains in the version, the picker is there but says why it can't be used.
  expect(within(dialog).getByLabelText(/Capability 1 domain/i)).toBeDisabled();
  await userEvent.type(within(dialog).getByLabelText(/Capability 1 matching phrases/i), "post invoice, journal");
  await userEvent.click(within(dialog).getByRole("button", { name: "Add constraint" }));
  await userEvent.type(within(dialog).getByLabelText("Constraint 1"), "Closed at month end{enter}");
  expect(within(dialog).getByLabelText("Constraint 2")).toHaveFocus();
  await userEvent.click(within(dialog).getByRole("button", { name: "Save system" }));

  const saved = save.mock.calls[0]?.[0];
  expect(saved?.systems.at(-1)).toEqual({
    id: "erp", name: "ERP", name_ar: null, aliases: ["Finance", "Ledger"], constraints: ["Closed at month end"],
    components: [], description: null, landscape_domain_id: null,
    capabilities: [{ id: "post", name: "Posting", triggers: ["post invoice", "journal"], domain_id: null,
      component_id: null }],
  });

  await userEvent.type(screen.getByRole("searchbox", { name: "Search systems" }), "bill");
  expect(screen.getByRole("button", { name: "Billing" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "BCRM" })).not.toBeInTheDocument();

  const dependencies = screen.getByRole("heading", { name: /Dependencies \(1\)/ }).parentElement;
  if (!dependencies) throw new Error("Expected the dependencies section.");
  await userEvent.click(within(dependencies).getByRole("button", { name: "Remove dependency BCRM → Billing" }));
  expect(save.mock.calls[1]?.[0].relationships).toEqual([]);
});

it("refuses a capability without matching phrases beside the field, and says where domains come from", async () => {
  const save = vi.spyOn(knowledgeApi, "save").mockResolvedValue(release({ revision: 4 }));

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  await userEvent.click(screen.getByRole("tab", { name: /Edit manually/ }));
  expect(screen.getByText(/This version has no capability domains/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "BCRM" }));
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByText("bcrm")).toBeVisible();
  expect(within(dialog).queryByLabelText(/System ID/)).not.toBeInTheDocument();
  await userEvent.click(within(dialog).getByRole("button", { name: /Capability 1:/ }));
  await userEvent.click(within(dialog).getByRole("button", { name: "Remove order" }));
  // The removed chip's button is gone, so focus lands in the field rather than on the page.
  const phrases = within(dialog).getByLabelText(/Capability 1 matching phrases/i);
  expect(phrases).toHaveFocus();
  await userEvent.click(within(dialog).getByRole("button", { name: "Save system" }));

  expect(save).not.toHaveBeenCalled();
  expect(phrases).toHaveFocus();
  expect(phrases).toHaveAccessibleDescription(/Add at least one matching phrase/);

  // Unsaved work is not thrown away by a stray Escape.
  // jsdom does not turn Escape into the dialog's cancel event, so send it directly.
  fireEvent(dialog, new Event("cancel", { bubbles: true, cancelable: true }));
  const discard = await screen.findByRole("dialog", { name: "Discard changes to BCRM?" });
  await userEvent.click(within(discard).getByRole("button", { name: "Cancel" }));
  expect(within(dialog).getByLabelText(/Capability 1 matching phrases/i)).toBeVisible();
  await userEvent.click(within(dialog).getByRole("button", { name: "Close" }));
  await userEvent.click(within(await screen.findByRole("dialog", { name: "Discard changes to BCRM?" }))
    .getByRole("button", { name: "Discard changes" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
});

it("removes a system with its dependencies after confirmation", async () => {
  const save = vi.spyOn(knowledgeApi, "save").mockResolvedValue(release({ revision: 4 }));

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  await userEvent.click(screen.getByRole("tab", { name: /Edit manually/ }));
  await userEvent.click(screen.getByRole("button", { name: "Remove BCRM" }));
  await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Remove system" }));

  expect(save.mock.calls[0]?.[0]).toMatchObject({
    systems: [expect.objectContaining({ id: "billing" })], relationships: [],
  });
});

it("downloads a version, shows its history and makes an earlier one active", async () => {
  const earlier = release({ id: "published-0", status: "published", published_at: "2026-08-01T09:00:00Z",
    published_by: "amina" });
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release(), active, earlier]);
  vi.spyOn(knowledgeApi, "audit").mockResolvedValue([{ release_id: "published-0", actor_id: "amina",
    action: "publish", revision: 3, rationale: "August review", created_at: "2026-08-01T09:00:00Z" }]);
  const download = vi.spyOn(knowledgeApi, "exportFile").mockResolvedValue(undefined);
  const activate = vi.spyOn(knowledgeApi, "activate").mockResolvedValue(earlier);

  renderPage();

  await openView("History");
  const table = await screen.findByRole("table", { name: "Catalogue versions" });
  await userEvent.selectOptions(screen.getByLabelText("Download format"), "json");
  await userEvent.click(within(table).getByRole("button", { name: "Download published-0 as JSON" }));
  expect(download).toHaveBeenCalledWith("published-0", "json");

  const [, , historyEarlier] = within(table).getAllByRole("button", { name: "Change log" });
  if (!historyEarlier) throw new Error("Expected a change log button per version.");
  await userEvent.click(historyEarlier);
  expect(await screen.findByText("“August review”")).toBeVisible();

  await userEvent.click(within(table).getByRole("button", { name: "Make active again" }));
  const dialog = await screen.findByRole("dialog");
  await userEvent.type(within(dialog).getByLabelText(/Why go back/), "Rollback after a bad import");
  await userEvent.click(within(dialog).getByRole("button", { name: "Make active" }));
  expect(activate).toHaveBeenCalledWith(earlier, "Rollback after a bad import");
});

it("shows each document's reading status from the server and explains a wait", async () => {
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([suggestion()]));
  vi.spyOn(knowledgeApi, "extractions").mockResolvedValue([
    { document_version_id: "doc-1", job: job("queued") },
  ]);
  vi.spyOn(knowledgeApi, "job").mockResolvedValue(job("queued"));

  renderPage();
  await openNext();

  expect(await screen.findByText("Waiting to start")).toBeVisible();
  expect(screen.getByText(/Waiting for the background worker/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Suggest from this document" })).not.toBeInTheDocument();
});

it("retries a failed reading job and says why it failed", async () => {
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([suggestion()]));
  const failed = { ...job("failed"), error_category: "attempts_exhausted" };
  vi.spyOn(knowledgeApi, "extractions").mockResolvedValue([{ document_version_id: "doc-1", job: failed }]);
  vi.spyOn(knowledgeApi, "job").mockResolvedValue(failed);
  const retry = vi.spyOn(knowledgeApi, "retryJob").mockResolvedValue(job("running"));

  renderPage();
  await openNext();

  expect(await screen.findByText(/tried three times without finishing/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(retry).toHaveBeenCalledOnce();
  expect(await screen.findByText(/Long documents on a local model/)).toBeVisible();
});

it("shows the build of record after a reload instead of starting another", async () => {
  vi.spyOn(knowledgeApi, "buildStatus").mockResolvedValue(job("running", "index"));
  vi.spyOn(knowledgeApi, "job").mockResolvedValue(job("running", "index"));
  const build = vi.spyOn(knowledgeApi, "build");

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 3: Build evidence index/ }));
  expect(await screen.findByText("Running")).toBeVisible();
  expect(screen.getByText("Building the index for your latest changes…")).toBeVisible();
  expect(build).not.toHaveBeenCalled();
});

it("builds and then publishes a version whose index is stale, naming the changes", async () => {
  const build = vi.spyOn(knowledgeApi, "build").mockResolvedValue(job("succeeded", "index"));
  const publish = vi.spyOn(knowledgeApi, "publish").mockResolvedValue(active);

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 4: Publish/ }));
  expect(screen.getByText(/it is built first, then this version is published/)).toBeVisible();
  await userEvent.type(screen.getByLabelText(/What did you check/), "Checked with the platform leads");
  await userEvent.click(screen.getByRole("button", { name: "Build and publish" }));
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByText(/Adds ERP\. New requirement mappings use it/)).toBeVisible();
  await userEvent.click(within(dialog).getByRole("button", { name: "Build and publish" }));

  expect(build).toHaveBeenCalledOnce();
  expect(await screen.findByText("Published. Requirement mapping now uses this version.")).toBeVisible();
  expect(publish.mock.calls[0]?.[0]).toMatchObject({ rationale: "Checked with the platform leads" });
});

it("lets a reader browse the systems in use, with what they do and who owns them", async () => {
  vi.spyOn(knowledgeApi, "me").mockResolvedValue({ ...maintainer, roles: ["knowledge_reader"] } as unknown as Actor);
  const releases = vi.spyOn(knowledgeApi, "releases");

  renderPage();

  expect(await screen.findByRole("heading", { name: "Systems in use" })).toBeVisible();
  const list = screen.getByRole("list", { name: "Systems in this version" });
  await userEvent.click(within(list).getByRole("button", { name: /^BCRM/ }));
  const bcrm = screen.getByRole("article", { name: "BCRM" });
  expect(within(bcrm).getByText("Ordering")).toBeVisible();
  expect(within(bcrm).getByText("Found by: order")).toBeVisible();
  expect(within(bcrm).getByText(/Bills orders/)).toBeVisible();
  expect(screen.getByText("Squad: Orders squad")).toBeVisible();
  expect(screen.getByText("Value stream: Digital sales")).toBeVisible();
  expect(screen.getByText("Product: Partner portal")).toBeVisible();
  // A dependency opens the other system's dossier, which names the way back.
  await userEvent.click(within(bcrm).getByRole("button", { name: "Billing" }));
  const billing = screen.getByRole("article", { name: "Billing" });
  expect(within(billing).getByRole("button", { name: "BCRM" })).toBeVisible();
  expect(within(billing).getByText("No squad owns this system yet.")).toBeVisible();
  await userEvent.type(screen.getByRole("searchbox", { name: "Search the catalogue" }), "bill");
  expect(screen.getByText("1 of 2 systems")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Start a new version" })).not.toBeInTheDocument();
  expect(releases).not.toHaveBeenCalled();
});

it("lets a maintainer browse the version in use next to the draft", async () => {
  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /^In use: / }));
  expect(screen.getByRole("heading", { name: "Systems in use" })).toBeVisible();
  expect(screen.getByRole("list", { name: "Systems in this version" })).toBeVisible();
  // The desk still carries the version in progress and its next step.
  expect(screen.getByRole("button", { name: /^Open / })).toBeVisible();
});

it("compares the saved samples with the version in use, row by row", async () => {
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release({ built_revision: 3 }), active]);
  vi.spyOn(knowledgeApi, "samples").mockResolvedValue({
    revision: 1, updated_by: "amina", updated_at: null,
    items: [{ id: "s1", text: "Partners order fibre" }, { id: "s2", text: "Bill the order" }],
  });
  const compare = vi.spyOn(knowledgeApi, "compareImpact")
    .mockResolvedValueOnce(compared(["BCRM"], ["BCRM", "Order Hub"]))
    .mockResolvedValueOnce(compared(["Billing"], ["Billing"]));

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 3: Build evidence index/ }));
  await userEvent.click(await screen.findByRole("button", { name: "Compare with the version in use" }));

  expect(await screen.findByText("Compared 2 of 2: 1 differs from the version in use.")).toBeVisible();
  expect(compare).toHaveBeenNthCalledWith(1, "draft-1", "Partners order fibre");
  expect(compare).toHaveBeenNthCalledWith(2, "draft-1", "Bill the order");
  expect(screen.getByText("Changed")).toBeVisible();
  expect(screen.getByText("+ Order Hub")).toBeVisible();
  expect(screen.getByText("Same systems")).toBeVisible();
});

it("adds a sample and saves the shared list with its revision", async () => {
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release({ built_revision: 3 }), active]);
  vi.spyOn(knowledgeApi, "samples").mockResolvedValue({
    revision: 4, updated_by: null, updated_at: null, items: [{ id: "s1", text: "Partners order fibre" }],
  });
  const save = vi.spyOn(knowledgeApi, "saveSamples").mockResolvedValue({
    revision: 5, updated_by: "editor", updated_at: null,
    items: [{ id: "s1", text: "Partners order fibre" }, { id: "s2", text: "Close the order in billing" }],
  });

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 3: Build evidence index/ }));
  await userEvent.type(await screen.findByLabelText("Add a sample"), "Close the order in billing");
  await userEvent.click(screen.getByRole("button", { name: "Add sample" }));
  await userEvent.click(screen.getByRole("button", { name: "Remove sample 1" }));
  await userEvent.click(screen.getByRole("button", { name: "Save samples" }));

  expect(save).toHaveBeenCalledWith(4, [{ text: "Close the order in billing" }]);
  expect(await screen.findByText("Partners order fibre")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Save samples" })).not.toBeInTheDocument();
});

it("stops a comparison after the requirement in progress", async () => {
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release({ built_revision: 3 }), active]);
  vi.spyOn(knowledgeApi, "samples").mockResolvedValue({
    revision: 1, updated_by: null, updated_at: null,
    items: [{ id: "s1", text: "First" }, { id: "s2", text: "Second" }],
  });
  let finish: (value: ReturnType<typeof compared>) => void = () => undefined;
  const compare = vi.spyOn(knowledgeApi, "compareImpact").mockImplementation(
    () => new Promise((resolve) => { finish = resolve; }),
  );

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 3: Build evidence index/ }));
  await userEvent.click(await screen.findByRole("button", { name: "Compare with the version in use" }));
  expect(await screen.findByText("Comparing 1 of 2…")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Stop" }));
  finish(compared([], ["BCRM"]));

  expect(await screen.findByText("Compared 1 of 2: 1 differs from the version in use.")).toBeVisible();
  expect(screen.getByText("Now finds systems")).toBeVisible();
  expect(compare).toHaveBeenCalledOnce();
});

it("names the version in progress and lets a maintainer rename or discard it", async () => {
  const named = release({ name: "October integration update", created_by: "amina" });
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([named, { ...active, name: "Initial catalogue" }]);
  const rename = vi.spyOn(knowledgeApi, "rename").mockResolvedValue({ ...named, name: "Q4 update", revision: 4 });
  const discard = vi.spyOn(knowledgeApi, "discard").mockResolvedValue(undefined);

  renderPage();

  expect(await screen.findByRole("heading", { name: "October integration update" })).toBeVisible();
  expect(screen.getByText(/started by amina/)).toBeVisible();
  await openView("History");
  const history = await screen.findByRole("table", { name: "Catalogue versions" });
  expect(within(history).getByText("Initial catalogue")).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Rename" }));
  const renaming = await screen.findByRole("dialog");
  await userEvent.clear(within(renaming).getByLabelText(/Version name/));
  await userEvent.type(within(renaming).getByLabelText(/Version name/), "Q4 update");
  await userEvent.click(within(renaming).getByRole("button", { name: "Rename" }));
  expect(rename).toHaveBeenCalledWith(expect.objectContaining({ id: "draft-1" }), "Q4 update");

  await userEvent.click(screen.getByRole("button", { name: "Remove this version" }));
  const confirm = await screen.findByRole("dialog");
  expect(within(confirm).getByText(/cannot be undone/)).toBeVisible();
  await userEvent.click(within(confirm).getByRole("button", { name: "Remove version" }));
  expect(discard).toHaveBeenCalledWith(expect.objectContaining({ id: "draft-1" }));
  expect(await screen.findByText("The version in progress was removed.")).toBeVisible();
});

it("says how much of the backlog still uses an older version and what publishing affects", async () => {
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release({ built_revision: 3 }), active]);
  vi.spyOn(knowledgeApi, "mappingImpact").mockResolvedValue(impact({
    requirements: 12, features: 30, stories: 84, outdated_requirements: 5,
  }));

  renderPage();

  expect(await screen.findByText(/5 requirements are still mapped with an older version/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /Step 4: Publish/ }));
  await userEvent.type(screen.getByLabelText(/What did you check/), "Checked");
  await userEvent.click(screen.getByRole("button", { name: "Publish this version" }));
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByText(/12 requirements \(30 features, 84 stories\)/)).toBeVisible();
  expect(within(dialog).getByText(/remapping resets their approvals/)).toBeVisible();
});

it("draws each system's neighbours with a label that says the same", async () => {
  vi.spyOn(knowledgeApi, "me").mockResolvedValue({ ...maintainer, roles: ["knowledge_reader"] } as unknown as Actor);

  renderPage();

  await screen.findByRole("heading", { name: "Systems in use" });
  expect(screen.getByRole("img", { name: "BCRM depends on 1 system and is used by 0." })).toBeInTheDocument();
  await userEvent.click(within(screen.getByRole("list", { name: "Systems in this version" }))
    .getByRole("button", { name: "Billing" }));
  expect(screen.getByRole("img", { name: "Billing depends on 0 systems and is used by 1." })).toBeInTheDocument();
});

it("groups suggestions by system and rejects a whole group after confirming", async () => {
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([
    suggestion(),
    suggestion({ id: "s-2", content: { kind: "constraint", system_id: "order-hub", name: "", name_ar: null,
      aliases: [], capability_id: null, triggers: [], target_system_id: null, text: "Read-only at night" } }),
    suggestion({ id: "s-3", content: { kind: "constraint", system_id: "bcrm", name: "", name_ar: null,
      aliases: [], capability_id: null, triggers: [], target_system_id: null, text: "Quotes expire in 30 days" } }),
  ]));
  const reject = vi.spyOn(knowledgeApi, "rejectSuggestions").mockResolvedValue({ rejected: 2 });

  renderPage();
  await openNext();

  await userEvent.click(await screen.findByRole("button", { name: "System" }));
  const hub = screen.getByRole("region", { name: "Order Hub" });
  expect(within(hub).getByText("Read-only at night")).toBeVisible();
  expect(screen.getByRole("region", { name: "BCRM" })).toBeVisible();
  await userEvent.click(within(hub).getByRole("button", { name: "Reject all 2 waiting in Order Hub" }));
  await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Reject all" }));

  expect(reject).toHaveBeenCalledWith(expect.objectContaining({ id: "draft-1" }), ["s-1", "s-2"]);
  expect(await screen.findByText("2 suggestions rejected.")).toBeVisible();
});

it("shows a cited passage in its document with the quote marked", async () => {
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([suggestion()]));
  const passage = vi.spyOn(knowledgeApi, "passage").mockResolvedValue({
    mime_type: "application/pdf",
    passage: { location: "paragraph 2", text: "Since 2024: The Order Hub captures orders from partners." },
    before: [{ location: "paragraph 1", text: "Ordering overview." }],
    after: [{ location: "paragraph 3", text: "Billing follows." }],
  });

  renderPage();
  await openNext();

  await userEvent.click(await screen.findByRole("button", { name: "Show paragraph 2 in Order design" }));
  const dialog = await screen.findByRole("dialog");
  expect(passage).toHaveBeenCalledWith("draft-1", "doc-1", "paragraph 2");
  expect(await within(dialog).findByText("The Order Hub captures orders", { selector: "mark" })).toBeVisible();
  expect(within(dialog).getByText("Ordering overview.")).toBeVisible();
  expect(within(dialog).getByText("Billing follows.")).toBeVisible();
});

it("explains that images feed suggestions only", async () => {
  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  expect(screen.getAllByText(/Images feed suggestions only/).length).toBeGreaterThan(0);
});

it("removes any version still in progress from the history, never a published one", async () => {
  const older = release({ id: "draft-0", name: "Left over draft", revision: 2 });
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release({ name: "October update" }), older, active]);
  const discard = vi.spyOn(knowledgeApi, "discard").mockResolvedValue(undefined);

  renderPage();

  await openView("History");
  const history = await screen.findByRole("table", { name: "Catalogue versions" });
  expect(within(history).getByRole("button", { name: "Remove October update" })).toBeVisible();
  expect(within(history).queryByRole("button", { name: /Remove published-1/ })).not.toBeInTheDocument();

  await userEvent.click(within(history).getByRole("button", { name: "Remove Left over draft" }));
  await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel" }));
  expect(discard).not.toHaveBeenCalled();

  await userEvent.click(within(history).getByRole("button", { name: "Remove Left over draft" }));
  await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Remove version" }));
  expect(discard).toHaveBeenCalledWith(expect.objectContaining({ id: "draft-0", revision: 2 }));
  expect(await screen.findByText("“Left over draft” was removed.")).toBeVisible();
  expect(screen.getByText("The version in progress was removed.")).toBeVisible();
});

it("reads the whole landscape as a dependency matrix and opens a system from it", async () => {
  vi.spyOn(knowledgeApi, "me").mockResolvedValue({ ...maintainer, roles: ["knowledge_reader"] } as unknown as Actor);

  renderPage();

  await openView("Dependencies");
  expect(screen.getByText("Select a mark to read that dependency.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "BCRM depends on Billing" }));
  expect(screen.getByRole("status")).toHaveTextContent("BCRM depends on Billing — Bills orders");
  await userEvent.click(screen.getByRole("button", { name: "Open Billing" }));
  expect(screen.getByRole("article", { name: "Billing" })).toBeVisible();
});

it("marks what the version in progress adds and removes, in words as well as colour", async () => {
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release({ name: "October update" }), active]);
  vi.spyOn(knowledgeApi, "changes").mockResolvedValue({
    base_release_id: "published-1", draft_release_id: "draft-1",
    changes: [
      { item: "relationship", change: "added", key: "bcrm->billing:bills orders",
        label: "BCRM → Billing: Bills orders", fields: [] },
      { item: "relationship", change: "removed", key: "billing->bcrm:returns credit",
        label: "Billing → BCRM: Returns credit", fields: [] },
      { item: "system", change: "removed", key: "legacy", label: "Legacy CRM", fields: [] },
    ],
  });

  renderPage();

  await openView("Systems");
  const list = await screen.findByRole("list", { name: "Systems in this version" });
  expect(await within(list).findByText("Legacy CRM")).toBeVisible();
  expect(within(list).getAllByText("Changed")).toHaveLength(2);
  await openView("Dependencies");
  expect(screen.getByRole("button", { name: "BCRM depends on Billing, added in this version" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Billing depends on BCRM, removed in this version" })).toBeVisible();
  expect(screen.getByText("Added in this version (1)")).toBeVisible();
});

it("points an empty review back to adding content", async () => {
  vi.spyOn(knowledgeApi, "changes").mockResolvedValue({
    base_release_id: "published-1", draft_release_id: "draft-1", changes: [],
  });

  renderPage();
  await openNext();

  expect(await screen.findByText(/Nothing differs from the version in use yet/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Add content" }));
  expect(screen.getByRole("button", { name: /Step 1: Add content/, current: "step" })).toBeVisible();
});

it("lands on the systems of the version in progress, with the next step on the desk", async () => {
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([release({ name: "October update" }), active]);

  renderPage();

  expect(await screen.findByRole("heading", { name: "Systems in this version" })).toBeVisible();
  expect(screen.queryByRole("button", { current: "step" })).not.toBeInTheDocument();
  await openNext();
  expect(screen.getByRole("button", { name: /Step 2: Review changes/, current: "step" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Back to systems" }));
  expect(screen.getByRole("heading", { name: "Systems in this version" })).toBeVisible();
});

it("says in one line what the version in progress does, and groups what follows from a removed system", async () => {
  vi.spyOn(knowledgeApi, "active").mockResolvedValue({
    ...active,
    systems: [...active.systems, { id: "legacy", name: "Legacy CRM", name_ar: null, aliases: [], capabilities: [], constraints: [] }],
  });
  vi.spyOn(knowledgeApi, "changes").mockResolvedValue({
    base_release_id: "published-1", draft_release_id: "draft-1",
    changes: [
      { item: "system", change: "removed", key: "legacy", label: "Legacy CRM", fields: [] },
      { item: "relationship", change: "removed", key: "legacy->billing:sends invoices",
        label: "Legacy CRM → Billing: Sends invoices", fields: [] },
    ],
  });

  renderPage();

  expect(await screen.findByText("Removes Legacy CRM · 1 dependency removed · touches 1 other system")).toBeVisible();
  // A removed system still opens, as it stands in the version in use.
  await userEvent.click(within(screen.getByRole("list", { name: "Systems in this version" }))
    .getByRole("button", { name: /Legacy CRM/ }));
  const legacy = screen.getByRole("article", { name: "Legacy CRM" });
  expect(within(legacy).getByText(/This version removes it/)).toBeVisible();
  await openNext();
  await waitFor(() => expect(screen.getByRole("heading", { name: "Review what this version changes" })).toHaveFocus());
  expect(screen.getByText("Removed with it (1)")).toBeVisible();
  expect(screen.queryByRole("region", { name: "Dependency changes" })).not.toBeInTheDocument();
});

it("opens a step, a view and a system from the address", async () => {
  renderPage("/architecture-knowledge?step=publish");
  expect(await screen.findByRole("heading", { name: "Publish this version" })).toBeVisible();
  expect(screen.getByRole("button", { name: /Step 4: Publish/, current: "step" })).toBeVisible();
});

it("moves through the systems with the arrow keys as one tab stop", async () => {
  vi.spyOn(knowledgeApi, "me").mockResolvedValue({ ...maintainer, roles: ["knowledge_reader"] } as unknown as Actor);

  renderPage("/architecture-knowledge?system=bcrm");

  const list = await screen.findByRole("list", { name: "Systems in this version" });
  const bcrm = within(list).getByRole("button", { name: /^BCRM/ });
  expect(within(list).getByRole("button", { name: "Billing" })).toHaveAttribute("tabindex", "-1");
  bcrm.focus();
  await userEvent.keyboard("{ArrowDown}");
  expect(await screen.findByRole("article", { name: "Billing" })).toBeVisible();
  await waitFor(() => expect(within(list).getByRole("button", { name: "Billing" })).toHaveFocus());
});

it("asks before accepting every waiting AI suggestion, and before removing a source document", async () => {
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([suggestion()]));
  const acceptAll = vi.spyOn(knowledgeApi, "acceptAll").mockResolvedValue({ accepted: 1, remaining: 0 } as never);
  const select = vi.spyOn(knowledgeApi, "selectDocuments");

  renderPage();
  await openNext();

  await userEvent.click(screen.getByRole("button", { name: "Accept all 1 waiting" }));
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByText(/without checking each one against its source passage: 1 system\./)).toBeVisible();
  await userEvent.click(within(dialog).getByRole("button", { name: "Accept all" }));
  expect(acceptAll).toHaveBeenCalledOnce();

  await userEvent.click(screen.getByRole("button", { name: "Remove Order design from this version" }));
  await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel" }));
  expect(select).not.toHaveBeenCalled();
});

it("remembers a finished review after a reload, and says so when working ahead of an unfinished step", async () => {
  const first = renderPage("/architecture-knowledge?step=review");
  await userEvent.click(await screen.findByRole("button", { name: "These changes are right — continue" }));
  expect(screen.getByRole("button", { name: /Step 2: Review changes, done/ })).toBeVisible();
  first.unmount();

  renderPage("/architecture-knowledge?step=publish");
  expect(await screen.findByRole("button", { name: /Step 2: Review changes, done/ })).toBeVisible();
  // Build is the first unfinished step, and Publish says so without blocking.
  expect(screen.getByText(/Build evidence index isn’t done yet/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Build and publish" })).toBeVisible();
});

const withComponents = (changes: Partial<KnowledgeRelease> = {}) => release({
  systems: [
    { id: "bcrm", name: "BCRM", name_ar: null, aliases: ["CRM"], constraints: [],
      components: [
        { id: "sales-ui", name: "Sales UI", name_ar: null, aliases: ["Agent desk"], technology: "Web app",
          description: "Where agents take orders." },
        { id: "quotes", name: "Quote engine", name_ar: null, aliases: [], technology: null, description: null },
      ],
      capabilities: [
        { id: "order", name: "Ordering", triggers: ["order"], component_id: "sales-ui" },
        { id: "notify", name: "Notifying", triggers: ["notify"] },
      ] },
    { id: "billing", name: "Billing", name_ar: null, aliases: [], constraints: [],
      capabilities: [{ id: "bill", name: "Invoicing", triggers: ["bill"], domain_id: null }] },
  ],
  ...changes,
});

it("keeps system components: adds one, places a capability in it, and will not remove one in use", async () => {
  const save = vi.spyOn(knowledgeApi, "save").mockResolvedValue(release({ revision: 4 }));
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([withComponents(), active]);

  renderPage();

  await userEvent.click(await screen.findByRole("button", { name: /Step 1: Add content/ }));
  await userEvent.click(screen.getByRole("tab", { name: /Edit manually/ }));
  const table = screen.getByRole("table", { name: /Systems in this version/ });
  const header = within(table).getAllByRole("columnheader").map((cell) => cell.textContent);
  expect(within(within(table).getByRole("row", { name: /BCRM/ })).getAllByRole("cell")[header.indexOf("Components")])
    .toHaveTextContent("2");

  await userEvent.click(screen.getByRole("button", { name: "BCRM" }));
  const bcrm = await screen.findByRole("dialog");
  expect(within(bcrm).getByRole("heading", { name: "Components (2)" })).toBeVisible();
  const salesUi = within(bcrm).getByRole("button", { name: /Component 1: Sales UI/ });
  expect(salesUi).toHaveAccessibleName("Component 1: Sales UI, ID sales-ui, Web app, Delivers 1 capability");
  const remove = within(bcrm).getByRole("button", { name: "Remove component 1" });
  expect(remove).toHaveAttribute("aria-disabled", "true");
  expect(remove).toHaveAccessibleDescription(
    "Delivers 1 capability. Move it to another component before removing it.");
  await userEvent.click(remove);
  expect(within(bcrm).getByRole("button", { name: /Component 1: Sales UI/ })).toBeVisible();
  expect(within(bcrm).getByRole("button", { name: /Capability 1: Ordering.*in Sales UI/ })).toBeVisible();
  // An untouched drawer closes without asking.
  await userEvent.click(within(bcrm).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Billing" }));
  const billing = await screen.findByRole("dialog");
  await userEvent.click(within(billing).getByRole("button", { name: /Capability 1:/ }));
  expect(within(billing).getByLabelText(/Capability 1 component/i)).toBeDisabled();
  await userEvent.click(within(billing).getByRole("button", { name: "Add component" }));
  expect(within(billing).getByLabelText(/Component 1 name/i)).toHaveFocus();
  await userEvent.type(within(billing).getByLabelText(/Component 1 name/i), "Invoicing engine");
  expect(within(billing).getByLabelText(/Component 1 ID/i)).toHaveValue("invoicing-engine");
  await userEvent.type(within(billing).getByLabelText(/Component 1 technology/i), "Batch job");
  await userEvent.selectOptions(within(billing).getByLabelText(/Capability 1 component/i), "Invoicing engine");
  // Changing the component's ID afterwards keeps the capability pointed at it.
  await userEvent.clear(within(billing).getByLabelText(/Component 1 ID/i));
  await userEvent.type(within(billing).getByLabelText(/Component 1 ID/i), "invoicing");
  expect(within(billing).getByText("Delivers “Invoicing”.")).toBeVisible();
  await userEvent.click(within(billing).getByRole("button", { name: "Save system" }));

  const saved = save.mock.calls[0]?.[0].systems.find((item) => item.id === "billing");
  expect(saved?.components).toEqual([{ id: "invoicing", name: "Invoicing engine", name_ar: null, aliases: [],
    technology: "Batch job", description: null }]);
  expect(saved?.capabilities[0]?.component_id).toBe("invoicing");
});

it("groups what a system does by the component that delivers it", async () => {
  vi.spyOn(knowledgeApi, "me").mockResolvedValue({ ...maintainer, roles: ["knowledge_reader"] } as unknown as Actor);
  vi.spyOn(knowledgeApi, "active").mockResolvedValue({ ...withComponents(), ...active, systems: withComponents().systems });

  renderPage();

  const list = await screen.findByRole("list", { name: "Systems in this version" });
  await userEvent.click(within(list).getByRole("button", { name: /^BCRM/ }));
  const bcrm = screen.getByRole("article", { name: "BCRM" });
  expect(within(bcrm).getByRole("heading", { name: /^What it does/, level: 4 }))
    .toHaveTextContent("What it does (2 capabilities in 2 components)");
  const row = (name: string) => {
    const item = within(bcrm).getByRole("heading", { name, level: 5 }).closest("li");
    if (!item) throw new Error(`Expected the ${name} row.`);
    return item;
  };
  const salesUi = row("Sales UI");
  expect(within(salesUi).getByText("Web app · also called Agent desk")).toBeVisible();
  expect(within(salesUi).getByText("Where agents take orders.")).toBeVisible();
  expect(within(salesUi).getByText("Ordering")).toBeVisible();
  expect(within(row("Quote engine")).getByText("No capabilities placed here yet.")).toBeVisible();
  expect(within(row("Not in a component")).getByText("Notifying")).toBeVisible();
  // Components are headings inside the dossier, not landmarks of their own.
  expect(within(bcrm).queryByRole("region", { name: "Sales UI" })).not.toBeInTheDocument();

  // A system without components reads as before.
  await userEvent.click(within(list).getByRole("button", { name: /^Billing/ }));
  const billing = screen.getByRole("article", { name: "Billing" });
  expect(within(billing).queryByRole("heading", { name: "Not in a component" })).not.toBeInTheDocument();
  expect(within(billing).getByText("Invoicing")).toBeVisible();
});

it("reviews suggested components, and says when a capability waits for its component", async () => {
  vi.spyOn(knowledgeApi, "releases").mockResolvedValue([withComponents(), active]);
  vi.spyOn(knowledgeApi, "suggestions").mockResolvedValue(overview([
    suggestion({ id: "s-c", content: { kind: "component", system_id: "bcrm", name: "Pricing service", name_ar: null,
      aliases: [], capability_id: null, triggers: [], target_system_id: null, text: "", component_id: "pricing-service",
      technology: "Microservice", description: "Prices each quote." }, system_name: "BCRM" }),
    suggestion({ id: "s-p", match: "needs_component", content: { kind: "capability", system_id: "bcrm",
      name: "Pricing", name_ar: null, aliases: [], capability_id: "pricing", triggers: ["price"],
      target_system_id: null, text: "", component_id: "pricing-service" }, system_name: "BCRM" }),
  ]));
  const decide = vi.spyOn(knowledgeApi, "decide").mockResolvedValue(release({ revision: 4 }));

  renderPage();
  await openNext();

  const components = await screen.findByRole("region", { name: "Components" });
  expect(within(components).getByText("Pricing service — BCRM")).toBeVisible();
  expect(within(components).getByText("Microservice · Prices each quote.")).toBeVisible();
  const capabilities = screen.getByRole("region", { name: "Capabilities" });
  expect(within(capabilities).getByText("Matching phrases: price · Delivered by Pricing service")).toBeVisible();
  expect(within(capabilities).getByText("Needs its component first")).toBeVisible();

  await userEvent.click(within(capabilities).getByRole("button", { name: "Edit and accept Pricing — BCRM" }));
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByLabelText("Component")).toHaveValue("pricing-service");
  await userEvent.selectOptions(within(dialog).getByLabelText("Component"), "Quote engine");
  await userEvent.click(within(dialog).getByRole("button", { name: "Accept with these edits" }));

  expect(decide).toHaveBeenCalledWith(expect.anything(), "s-p", true,
    expect.objectContaining({ component_id: "quotes", name: "Pricing" }));
});
