import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { RevisionHistory } from "../../api/client";
import { RevisionPanel } from "./RevisionPanel";
import { readChange, wordDiff } from "./labels";

const history: RevisionHistory = {
  requirement_revisions: [
    {
      number: 1,
      created_at: "2026-01-01T00:00:00Z",
      title: "Transfer funds",
      description: "Human source",
      status: "draft",
    },
  ],
  breakdown_revisions: [
    {
      number: 1,
      created_at: "2026-01-01T00:01:00Z",
      has_analysis: true,
      analysis_human_confirmed: false,
      clarification_count: 0,
      unresolved_count: 2,
      intent_proposal_count: 1,
      intent_decision_count: 0,
      epic_name: null,
      epic_status: null,
      feature_count: 0,
      approved_feature_count: 0,
      story_count: 0,
      edited_story_count: 0,
      stale_story_count: 0,
      has_review: false,
      review_blocker_count: 0,
      review_decision_count: 0,
      review_status: null,
      approval_count: 0,
      comment_count: 0,
      submitted_fingerprint: null,
      exportable: false,
      final_approved_by: null,
      final_approved_at: null,
    },
    {
      number: 2,
      created_at: "2026-01-01T00:02:00Z",
      has_analysis: true,
      analysis_human_confirmed: false,
      clarification_count: 2,
      unresolved_count: 0,
      intent_proposal_count: 1,
      intent_decision_count: 1,
      epic_name: "Safe transfer",
      epic_status: "generated",
      feature_count: 0,
      approved_feature_count: 0,
      story_count: 2,
      edited_story_count: 1,
      stale_story_count: 0,
      has_review: true,
      review_blocker_count: 1,
      review_decision_count: 2,
      review_status: "generated",
      approval_count: 0,
      comment_count: 0,
      submitted_fingerprint: null,
      exportable: false,
      final_approved_by: null,
      final_approved_at: null,
    },
  ],
};

const approvedHistory: RevisionHistory = {
  ...history,
  breakdown_revisions: [
    ...history.breakdown_revisions.map((revision) =>
      revision.number === 2
        ? {
            ...revision,
            review_status: "approved",
            exportable: true,
            final_approved_by: { id: "owner-1", display_name: "Amina Owner", email: "amina@example.test", roles: [] },
            final_approved_at: "2026-01-01T00:03:00Z",
          }
        : revision,
    ),
    {
      ...history.breakdown_revisions[1]!,
      number: 3,
      created_at: "2026-01-01T00:04:00Z",
      review_status: "needs_revision",
      stale_story_count: 2,
    },
  ],
};

type PanelProps = Parameters<typeof RevisionPanel>[0];

function renderPanel(overrides: Partial<PanelProps> = {}) {
  const props: PanelProps = {
    history,
    comparison: null,
    busy: false,
    error: null,
    exportError: null,
    exportingRevision: null,
    canExportApprovedRevisions: true,
    onCompare: vi.fn(),
    onDownload: vi.fn(),
    ...overrides,
  };
  render(<MemoryRouter><RevisionPanel {...props} /></MemoryRouter>);
  return props;
}

describe("RevisionPanel", () => {
  it("lists backlog and business need versions newest first, with their status in words", async () => {
    const props = renderPanel({ reviewHref: "/requirements/req-1/review" });

    expect(screen.getByRole("heading", { name: "Nothing is approved for export yet" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Go to Review & approve" })).toHaveAttribute("href", "/requirements/req-1/review");
    const rows = within(screen.getByRole("table", { name: "Backlog versions, newest first" })).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("2");
    expect(rows[1]).toHaveTextContent("Current");
    expect(rows[1]).toHaveTextContent("Stories drafted");
    expect(rows[2]).toHaveTextContent("2 unresolved questions");
    expect(screen.getByText("Transfer funds")).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "Compare" }));
    expect(props.onCompare).toHaveBeenCalledWith(1, 2);
  });

  it("shows what changed as before-and-after facts, with ID lists folded into counts", () => {
    renderPanel({
      comparison: {
        from_revision: 1,
        to_revision: 2,
        changes: [
          "Requirement analysis or human clarifications changed.",
          "Stories added: story-a, story-b.",
        ],
      },
    });

    expect(screen.getByRole("heading", { name: "Version 1 to version 2" })).toHaveFocus();
    const facts = screen.getByRole("table", { name: "What changed from version 1 to version 2" });
    expect(within(facts).getByRole("row", { name: /Stories 0 2/ })).toBeVisible();
    expect(within(facts).getByRole("row", { name: /Unresolved questions 2 0/ })).toBeVisible();
    expect(screen.getByText("Requirement analysis or human clarifications changed.")).toBeVisible();
    expect(screen.getByText("2 stories added.")).toBeVisible();
  });

  it("reads the server's ID lists as counts", () => {
    expect(readChange("Features changed: a, b.")).toEqual({ text: "2 features changed.", ids: ["a", "b"] });
    expect(readChange("Stories removed: x.")).toEqual({ text: "1 story removed.", ids: ["x"] });
    expect(readChange("Epic content changed.")).toEqual({ text: "Epic content changed.", ids: [] });
  });

  it("leads with the approved export, says what changed since, and downloads the chosen format", async () => {
    const props = renderPanel({ history: approvedHistory, exported: { revision: 2, format: "json" } });

    expect(screen.getByRole("heading", { name: /Approved backlog/ })).toBeVisible();
    expect(screen.getByText(/Approved by Amina Owner/)).toBeVisible();
    expect(screen.getByText(/The backlog is now version 3: needs revision, with 2 stories out of date/)).toBeVisible();
    expect(screen.getByText("Downloaded version 2 as JSON.")).toBeVisible();

    await userEvent.click(screen.getByRole("radio", { name: /Excel workbook/ }));
    await userEvent.click(screen.getByRole("button", { name: "Download version 2" }));
    expect(props.onDownload).toHaveBeenCalledWith(2, "xlsx");

    await userEvent.click(screen.getByRole("button", { name: "Compare version 2 with the current backlog" }));
    expect(props.onCompare).toHaveBeenCalledWith(2, 3);
  });

  it("keeps the download button focusable while the file is prepared, and ignores a second press", async () => {
    const props = renderPanel({ history: approvedHistory, exportingRevision: 2 });
    const button = screen.getByRole("button", { name: "Preparing version 2…" });
    expect(button).toBeEnabled();
    await userEvent.click(button);
    expect(props.onDownload).not.toHaveBeenCalled();
  });

  it("explains a restricted export without offering its controls", () => {
    renderPanel({ history: approvedHistory, canExportApprovedRevisions: false });
    expect(screen.getByText(/Only the requirement owner and its reviewers can download/)).toBeVisible();
    expect(screen.queryByRole("button", { name: /Download/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Format" })).not.toBeInTheDocument();
  });

  it("reports a failed download beside the button", () => {
    renderPanel({ history: approvedHistory, exportError: "The approved export could not be downloaded." });
    expect(screen.getByRole("alert")).toHaveTextContent("The approved export could not be downloaded.");
  });

  it("says when the approval was signed against an earlier business need, and shows the edit word by word", () => {
    renderPanel({
      history: {
        ...approvedHistory,
        requirement_revisions: [
          ...history.requirement_revisions,
          { number: 2, created_at: "2026-01-01T00:05:00Z", title: "Transfer funds", description: "Human source, reviewed", status: "draft" },
        ],
      },
    });
    expect(screen.getByRole("heading", { name: "Approved against an earlier business need" })).toBeVisible();
    expect(screen.getByText(/approved against business need version 1\. The need is now version 2/)).toBeVisible();
    expect(screen.getByText("The approved backlog was built from this")).toBeVisible();
    expect(screen.getByText(/The download above is version 2, exactly as it was approved/)).toBeVisible();
    const added = [...document.querySelectorAll("ins")].map((element) => element.textContent).join(" ");
    expect(added).toContain("reviewed");
    expect(added).toContain("[added:");
  });

  it("marks the versions a long history folds away", async () => {
    const many: RevisionHistory = {
      ...history,
      breakdown_revisions: Array.from({ length: 12 }, (_, index) => ({ ...history.breakdown_revisions[0]!, number: index + 1 })),
    };
    renderPanel({ history: many });
    expect(screen.getByText("Versions 1 to 6 are folded away")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Show all 12 versions" }));
    expect(screen.queryByText(/folded away/)).not.toBeInTheDocument();
  });

  it("diffs text by words", () => {
    expect(wordDiff("one two three", "one 2 three")).toEqual([
      { kind: "same", text: "one " },
      { kind: "removed", text: "two" },
      { kind: "added", text: "2" },
      { kind: "same", text: " three" },
    ]);
  });
});
