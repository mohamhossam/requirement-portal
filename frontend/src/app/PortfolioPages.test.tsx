import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, type ActivityEvent, type ActivityList, type OperationalReport, type RequirementList } from "../api/client";
import { renderWithClient } from "../test/renderWithClient";
import { ActivityPage } from "./ActivityPage";
import { ReportsPage } from "./ReportsPage";

const count = (value: number, id: string) => ({ value, evidence_event_ids: [id] });

const event = (overrides: Partial<ActivityEvent>): ActivityEvent => ({
  id: "event-1",
  requirement_id: "req-1",
  requirement_title: "Fibre",
  category: "requirement",
  action: "requirement_created",
  summary: "Requirement created",
  occurred_at: "2026-09-04T08:00:00Z",
  actor: { id: "actor-1", display_name: "Amina", email: null, roles: [] },
  target_id: "req-1",
  resource_path: "/requirements/req-1/capture",
  sources: [{ kind: "requirement_revision", source_id: "req-1:1" }],
  ...overrides,
});

const page = (items: ActivityEvent[], extra: Partial<ActivityList> = {}): ActivityList => ({
  total: items.length, offset: 0, limit: 100, has_more: false, items, ...extra,
});

const renderActivity = (entry = "/activity") =>
  renderWithClient(<MemoryRouter initialEntries={[entry]}><ActivityPage /></MemoryRouter>);

describe("activity", () => {
  beforeEach(() => {
    vi.spyOn(api, "listRequirements").mockResolvedValue({
      requirements: [{ id: "req-1", title: "Fibre" }, { id: "req-2", title: "Legacy" }],
    } as unknown as RequirementList);
    vi.spyOn(api, "searchActors").mockResolvedValue([
      { id: "actor-1", display_name: "Amina", email: "amina@example.test", roles: [] },
    ]);
  });
  afterEach(() => vi.restoreAllMocks());

  it("lists events by day, naming the requirement, the person and the record", async () => {
    vi.spyOn(api, "listActivity").mockResolvedValue(page([
      event({}),
      event({ id: "event-2", requirement_id: "req-2", requirement_title: "Legacy", category: "governance", action: "breakdown_submitted", summary: "Breakdown submitted for review", occurred_at: "2026-09-03T08:00:00Z", actor: null, resource_path: "/requirements/req-2/review", sources: [{ kind: "ai_job", source_id: "0cf0e4c4-aaaa-bbbb-cccc-000000000000" }] }),
    ]));
    renderActivity();
    await screen.findAllByRole("link", { name: "Fibre" });
    expect(screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent)).toHaveLength(2);
    expect(screen.getByRole("cell", { name: /Requirement created/ })).toBeVisible();
    expect(screen.getAllByText("Amina")[0]).toBeVisible();
    expect(screen.getAllByText("Not recorded")[0]).toBeVisible();
    expect(screen.getAllByRole("link", { name: "Fibre" })[0]).toHaveAttribute("href", "/requirements/req-1/capture");
    expect(screen.getAllByText("Requirement version 1")[0]).toBeVisible();
    expect(screen.getAllByText("0cf0e4c4")[0]).toBeVisible();
    expect(screen.getByText("2 events")).toHaveAttribute("role", "status");
  });

  it("shows a report's deep link in the controls it filters by", async () => {
    const list = vi.spyOn(api, "listActivity").mockResolvedValue(page([event({ action: "question_resolved", category: "clarification" })]));
    renderActivity("/activity?action=question_resolved&occurred_from=2026-09-21T00:00:00Z&occurred_before=2026-09-28T00:00:00Z");
    await screen.findAllByRole("link", { name: "Fibre" });
    expect(screen.getByRole("combobox", { name: "What happened" })).toHaveValue("action:question_resolved");
    expect(screen.getByLabelText("From")).toHaveValue("2026-09-21");
    expect(screen.getByLabelText("Before")).toHaveValue("2026-09-28");
    expect(list).toHaveBeenLastCalledWith(expect.objectContaining({
      actions: ["question_resolved"],
      occurredFrom: "2026-09-21T00:00:00Z",
      occurredBefore: "2026-09-28T00:00:00Z",
    }));
  });

  it("filters by a requirement chosen by name, not by ID", async () => {
    const list = vi.spyOn(api, "listActivity").mockResolvedValue(page([event({})]));
    renderActivity();
    await screen.findAllByRole("link", { name: "Fibre" });
    const picker = screen.getByRole("combobox", { name: "Requirement" });
    await userEvent.type(picker, "Leg");
    await userEvent.click(await within(screen.getByRole("listbox", { name: "Requirement" })).findByRole("option", { name: /Legacy/ }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ requirementId: "req-2" })));
    expect(screen.getByRole("button", { name: "Clear requirement" })).toBeVisible();
  });

  it("never applies a choice the person did not move to", async () => {
    const list = vi.spyOn(api, "listActivity").mockResolvedValue(page([event({})]));
    renderActivity();
    await screen.findAllByRole("link", { name: "Fibre" });
    const picker = screen.getByRole("combobox", { name: "Person" });
    await userEvent.click(picker);
    await userEvent.keyboard("{Enter}");
    expect(list).not.toHaveBeenCalledWith(expect.objectContaining({ actorId: "actor-1" }));
    expect(picker).not.toHaveAttribute("aria-activedescendant");
    await userEvent.keyboard("{ArrowDown}");
    expect(picker).toHaveAttribute("aria-activedescendant");
    expect(within(screen.getByRole("listbox", { name: "Person" })).getByRole("option", { selected: true })).toHaveTextContent("Amina");
    await userEvent.keyboard("{Enter}");
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ actorId: "actor-1" })));
  });

  it("says how many events are not shown, and loads the next page", async () => {
    const first = page([event({})], { total: 150, has_more: true });
    const list = vi.spyOn(api, "listActivity")
      .mockResolvedValueOnce(first)
      .mockResolvedValue(page([event({ id: "event-2", summary: "Answer recorded" })], { total: 150, offset: 100, has_more: false }));
    renderActivity();
    expect(await screen.findByText("Showing 1 of 150 events")).toHaveAttribute("role", "status");
    await userEvent.click(screen.getByRole("button", { name: /Show 100 more/ }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 1 })));
    expect(await screen.findByText("Answer recorded")).toBeVisible();
  });
});

describe("reports", () => {
  afterEach(() => vi.restoreAllMocks());

  it("leads with blockers by age, and links each count to its evidence", async () => {
    const report: OperationalReport = {
      generated_at: "2026-09-04T12:00:00Z", window_start: "2026-08-10T00:00:00Z", window_end: "2026-09-04T12:00:00Z", weeks: 4,
      clarification: { opened: count(2, "opened"), resolved: count(1, "resolved"), resolution_percentage: 50, median_resolution_hours: 0.4 },
      weekly: [{ week_start: "2026-08-31T00:00:00Z", week_end: "2026-09-04T12:00:00Z", requirements_created: count(3, "created"), analysis_rounds: count(2, "analysis"), clarifications_resolved: count(1, "resolved"), artifact_approvals: count(0, "approved"), breakdown_approvals: count(1, "final") }],
      oldest_blockers: [{ id: "question:q-1", requirement_id: "req-1", requirement_title: "Fibre", title: "Who owns fallout?", opened_at: "2026-08-20T00:00:00Z", actor: null, resource_path: "/requirements/req-1/clarify", source: { kind: "clarification_question", source_id: "q-1" } }],
    };
    vi.spyOn(api, "getOperationalReport").mockResolvedValue(report);
    renderWithClient(<MemoryRouter initialEntries={["/reports?weeks=4"]}><ReportsPage /></MemoryRouter>);

    const headings = await screen.findAllByRole("heading", { level: 2 });
    expect(headings.map((heading) => heading.textContent)).toEqual(["Blocking now", "Resolution rate", "Weekly throughput"]);
    expect(screen.getByRole("link", { name: "Who owns fallout?" })).toHaveAttribute("href", "/requirements/req-1/clarify");
    expect(screen.getByText("15 days")).toBeVisible();
    expect(screen.getByText("Under an hour")).toBeVisible();

    await userEvent.click(screen.getByText("Weekly numbers, each linked to the activity it counts"));
    const metric = screen.getByRole("link", { name: /^3 requirements created, week of/ });
    expect(metric.getAttribute("href")).toContain("action=requirement_created");
    expect(screen.queryByRole("link", { name: /^0 / })).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "12 weeks" }));
    await waitFor(() => expect(api.getOperationalReport).toHaveBeenLastCalledWith(12));
  });
});
