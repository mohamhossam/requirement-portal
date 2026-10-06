import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { KnowledgeFinding, KnowledgeReview } from "../../api/client";
import { AuthContext, type AuthState } from "../../auth/authContext";
import { evidenceFieldLabel } from "../analysis/labels";
import { KnowledgeReviewPanel } from "./KnowledgeReviewPanel";
import { fieldLabel, findingVerdict, linkedRequirement } from "./labels";

const duplicate: KnowledgeFinding = {
  id: "finding-1",
  kind: "possible_duplicate",
  status: "open",
  version: 1,
  subject_requirement_id: "req-current",
  related_requirement_id: "req-related",
  rationale: "The observable outcome and channel scope overlap.",
  evidence: [
    {
      chunk_id: "chunk-title",
      requirement_id: "req-related",
      field: "title",
      excerpt: "Order business bundles online",
      evidence_path: "/requirements/req-related/capture",
      fingerprint: "title-fingerprint",
    },
    {
      chunk_id: "chunk-1",
      requirement_id: "req-related",
      field: "desired_outcome",
      excerpt: "Business customers can order through BCRM.",
      evidence_path: "/requirements/req-related/capture",
      fingerprint: "evidence-fingerprint",
    },
  ],
  resolution_statement: null,
  resolution_approvals: [],
  decisions: [],
};

const pending: KnowledgeFinding = {
  ...duplicate,
  id: "finding-2",
  kind: "possible_contradiction",
  status: "resolution_pending",
  version: 2,
  rationale: "Trusted requirement evidence expresses an opposing rule.",
  resolution_statement: "The exception applies only to overdue accounts.",
  decisions: [{
    kind: "resolution_proposed",
    actor: { id: "fake-owner", display_name: "Amina Owner", email: null },
    rationale: "The exception applies only to overdue accounts.",
    recorded_at: "2026-09-26T10:20:00Z",
  }],
};

const review: KnowledgeReview = {
  status: "action_required",
  current: true,
  ready: false,
  input_fingerprint: "screen-fingerprint",
  screen_id: "screen-1",
  provenance: {
    model: "knowledge-classifier",
    prompt_version: "knowledge-v1",
    generated_at: "2026-09-05T12:00:00Z",
  },
  reference_conflict_ids: [],
  findings: [duplicate],
};

function renderPanel(overrides: Partial<ComponentProps<typeof KnowledgeReviewPanel>> = {}, actorId = "fake-owner") {
  const onDecide = vi.fn();
  const onRetry = vi.fn();
  const auth = { actor: { id: actorId, display_name: "Amina Owner", email: null } } as unknown as AuthState;
  render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter>
        <KnowledgeReviewPanel
          requirementId="req-current"
          requirementTitle="Business bundles"
          requirementText="Business customers order bundles in the retail store."
          review={review}
          running={false}
          ensureOutcome={null}
          ensureJobId={null}
          canDecide
          busy={false}
          error={null}
          decisionError={null}
          onRetry={onRetry}
          onDecide={onDecide}
          {...overrides}
        />
      </MemoryRouter>
    </AuthContext.Provider>,
  );
  return { onDecide, onRetry };
}

describe("KnowledgeReviewPanel", () => {
  it("names the linked requirement by its title and labels each quote by its source", () => {
    renderPanel();
    const finding = screen.getByRole("article", { name: /Possible duplicate of Order business bundles online/ });
    expect(within(finding).getByRole("link", { name: "Order business bundles online" }))
      .toHaveAttribute("href", "/requirements/req-related/knowledge");
    expect(within(finding).getByText("Business customers can order through BCRM.")).toBeVisible();
    expect(within(finding).getByText((_, element) =>
      element?.tagName === "P" && element.textContent === "Order business bundles online · Desired outcome")).toBeVisible();
    // The title names the heading; it is not quoted again as evidence.
    expect(within(finding).queryByText("Title", { exact: false })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "1 overlap needs your decision" })).toBeVisible();
  });

  it("sets this requirement's own business need beside a match that cites only the other side", () => {
    renderPanel();
    const finding = screen.getByRole("article", { name: /Possible duplicate of/ });
    expect(within(finding).getByText("Business customers order bundles in the retail store.")).toBeVisible();
    expect(within(finding).getByText(/Business need, for comparison/)).toBeVisible();
  });

  it("asks whether the needs are the same before offering either decision", async () => {
    const user = userEvent.setup();
    const { onDecide } = renderPanel();
    expect(screen.queryByRole("button", { name: /Mark as distinct/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Close as duplicate/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Different needs — keep both" }));
    const reason = screen.getByLabelText("Why they are different needs");
    // Focus stays in the radio group: arrowing between choices must not
    // throw the caret into a field (WCAG 3.2.2).
    expect(screen.getByRole("radio", { name: "Different needs — keep both" })).toHaveFocus();
    const distinct = screen.getByRole("button", { name: "Mark as distinct" });
    // Gated, not disabled: it keeps its tab stop and says why.
    expect(distinct).toHaveAttribute("aria-disabled", "true");
    expect(distinct).toHaveAccessibleDescription("Say why they differ first.");
    await user.click(distinct);
    expect(onDecide).not.toHaveBeenCalled();

    await user.type(reason, "This launch targets a different legal entity.");
    await user.click(screen.getByRole("button", { name: "Mark as distinct" }));
    expect(onDecide).toHaveBeenCalledWith(duplicate, "distinct", "This launch targets a different legal entity.");
  });

  it("confirms a duplicate closure naming both requirements, with Cancel focused", async () => {
    const user = userEvent.setup();
    const { onDecide } = renderPanel();
    await user.click(screen.getByRole("radio", { name: "The same need — close this requirement" }));
    await user.click(screen.getByRole("button", { name: "Close as duplicate…" }));

    const dialog = screen.getByRole("dialog", { name: "Close this requirement as a duplicate?" });
    expect(dialog).toHaveTextContent("“Business bundles” will be closed and will point to “Order business bundles online”");
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    expect(onDecide).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "Close as duplicate" }));
    expect(onDecide).toHaveBeenCalledWith(duplicate, "duplicate", undefined);
  });

  it("points the related side to the other requirement's own step instead of closing", () => {
    renderPanel({ requirementId: "req-related" });
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Why they are different needs")).toBeVisible();
    expect(screen.getByRole("link", { name: "its own Knowledge step" }))
      .toHaveAttribute("href", "/requirements/req-current/knowledge");
  });

  it("shows people who cannot decide the evidence, and no decision controls", () => {
    renderPanel({ canDecide: false });
    expect(screen.getByText(/Only the owners of these two requirements can decide this/)).toBeVisible();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByText("Waiting for an owner’s decision")).toBeVisible();
  });

  it("names who proposed a resolution and says when it is waiting on the other owner", () => {
    renderPanel({ review: { ...review, findings: [{ ...pending, resolution_approvals: ["fake-owner"] }] } });
    expect(screen.getByText(/Proposed by Amina Owner/)).toBeVisible();
    expect(screen.getByText(/Accepted by 1 owner\./)).toBeVisible();
    expect(screen.getByText("Waiting for the other owner")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Accept shared resolution" })).not.toBeInTheDocument();
  });

  it("offers acceptance, filled, to an owner who has not accepted yet", async () => {
    const user = userEvent.setup();
    const { onDecide } = renderPanel({ review: { ...review, findings: [pending] } });
    expect(screen.getByText("No owner has accepted it yet.", { exact: false })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Accept shared resolution" }));
    expect(onDecide).toHaveBeenCalledWith(pending, "accept_resolution", undefined);
  });

  it("reports a failed decision inside the finding it was made on", () => {
    renderPanel({ decisionError: "The finding changed." });
    // Nothing has been decided yet, so the error has no card to sit in.
    expect(screen.getByRole("alert")).toHaveTextContent("The finding changed.");
  });

  it("shows terminal automatic attempts as manual retry only", async () => {
    const user = userEvent.setup();
    const { onRetry } = renderPanel({
      review: { ...review, status: "stale", current: false, ready: false, findings: [] },
      ensureOutcome: "manual_retry_required",
      ensureJobId: "job-failed",
    });
    expect(screen.getByText(/will not start again by itself/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Check out of date" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry knowledge screening" }));
    expect(onRetry).toHaveBeenCalledWith("job-failed");
  });

  it("never prints a raw status, kind or field name", () => {
    renderPanel({ review: { ...review, findings: [duplicate, pending] } });
    const text = document.body.textContent ?? "";
    for (const raw of ["_", "action required", "resolution pending", "resolution_proposed"]) {
      expect(text.toLowerCase()).not.toContain(raw);
    }
  });
});

describe("knowledge labels", () => {
  it("names fields, prefixed fields and unknown fields in words", () => {
    expect(fieldLabel("business_need")).toBe("Business need");
    expect(fieldLabel("clarification:open_question")).toBe("Clarification answer");
    expect(fieldLabel("proposal:9f2c")).toBe("Reference decision");
    expect(fieldLabel("attachment:doc-1:block-3")).toBe("Attachment passage");
    // Clarify's suggestions label the same evidence without its identifiers.
    expect(evidenceFieldLabel("attachment:doc-1:block-3")).toBe("Attachment passage");
    expect(fieldLabel("something_new")).toBe("Something new");
  });

  it("falls back to a short ID when the evidence carries no title", () => {
    expect(linkedRequirement({ ...duplicate, evidence: [] }, "req-current").name).toBe("requirement req-rela");
  });

  it("keeps green for settled findings only", () => {
    const who = { canDecide: true, actorId: "fake-owner" };
    expect(findingVerdict(duplicate, who)).toEqual({ label: "Needs your decision", tone: "warning" });
    expect(findingVerdict(pending, who).tone).toBe("warning");
    expect(findingVerdict({ ...pending, resolution_approvals: ["fake-owner"] }, who).tone).toBe("neutral");
    expect(findingVerdict({ ...pending, status: "resolved" }, who).tone).toBe("success");
  });
});
