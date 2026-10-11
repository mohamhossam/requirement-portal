import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { PublicationPreview, PublicationReport, PublicationStatus } from "../../api/client";
import { PublicationPanel } from "./PublicationPanel";

type Item = PublicationPreview["items"][number];

const epic: Item = { key: "e", kind: "epic", label: "Epic", title: "Online ordering", parent_key: null, acceptance_criteria_count: 0, owning_squad_name: null, location: "SMB", action: "create", external_id: null, url: null };
const feature: Item = { key: "f", kind: "feature", label: "Feature 1", title: "Order a line", parent_key: "e", acceptance_criteria_count: 0, owning_squad_name: "Billing", location: "SMB\\Billing", action: "create", external_id: null, url: null };
const story: Item = { key: "s", kind: "story", label: "Story 1.1", title: "As a customer, I want to order", parent_key: "f", acceptance_criteria_count: 2, owning_squad_name: "Billing", location: "SMB\\Billing", action: "create", external_id: null, url: null };

const preview: PublicationPreview = {
  requirement_id: "r-1",
  revision: 3,
  approval_fingerprint: "fp-3",
  target: {
    system: "Azure DevOps",
    project: "SMB",
    default_location: "SMB",
    details: [{ label: "Organization", value: "https://dev.azure.com/contoso" }],
  },
  counts: { epics: 1, features: 1, stories: 1 },
  items: [epic, feature, story],
  status: "not_published",
  published_revision: null,
  removed: [],
};

const base = {
  revision: 3,
  preview,
  previewLoading: false,
  unavailable: null,
  previewError: null,
  canPublish: true,
  publishing: false,
  report: null,
  publishError: null,
};

describe("PublicationPanel", () => {
  it("previews the target and every item, and publishes only after confirmation", async () => {
    const onPublish = vi.fn();
    render(<PublicationPanel {...base} onPublish={onPublish} />);

    expect(screen.getByRole("heading", { name: "Publish version 3 to Azure DevOps" })).toBeInTheDocument();
    expect(screen.getByText("1 Epic, 1 Features, 1 Stories")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Work items for version 3" });
    expect(within(table).getAllByText("SMB\\Billing")).toHaveLength(2);
    expect(within(table).getAllByText("Owned by Billing")).toHaveLength(2);

    await userEvent.click(screen.getByRole("button", { name: "Publish to Azure DevOps" }));
    expect(onPublish).not.toHaveBeenCalled();
    const dialog = screen.getByRole("dialog", { name: "Publish version 3?" });
    expect(within(dialog).getByText(/creates 3 work items in Azure DevOps project SMB/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));
    expect(onPublish).toHaveBeenCalledWith("fp-3");
  });

  it("does not offer publishing to someone who is not the owner", () => {
    render(<PublicationPanel {...base} canPublish={false} onPublish={vi.fn()} />);

    expect(screen.queryByRole("button", { name: /Publish/ })).not.toBeInTheDocument();
    expect(screen.getByText("Only the requirement’s owner can publish.")).toBeInTheDocument();
  });

  it("says when publishing is not set up, without a preview", () => {
    render(<PublicationPanel {...base} preview={null} unavailable="Publishing is not set up." onPublish={vi.fn()} />);

    expect(screen.getByText("Publishing is not set up.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("reports a partial publication item by item", () => {
    const report: PublicationReport = {
      requirement_id: "r-1",
      revision: 3,
      system: "Azure DevOps",
      project: "SMB",
      outcome: "partial",
      steps: [
        { key: "e", kind: "epic", label: "Epic", title: "Online ordering", status: "created", external_id: "41", url: "https://dev.azure.com/contoso/41", error: null },
        { key: "f", kind: "feature", label: "Feature 1", title: "Order a line", status: "failed", external_id: null, url: null, error: "Azure DevOps refused the item (400)." },
        { key: "s", kind: "story", label: "Story 1.1", title: "As a customer", status: "not_attempted", external_id: null, url: null, error: null },
      ],
    };
    render(<PublicationPanel {...base} report={report} onPublish={vi.fn()} />);

    expect(screen.getByRole("status")).toHaveTextContent("Partly published");
    expect(screen.getByRole("link", { name: /Open item 41/ })).toHaveAttribute("href", "https://dev.azure.com/contoso/41");
    expect(screen.getByText("Azure DevOps refused the item (400).")).toBeInTheDocument();
    expect(screen.getByText("Not sent")).toBeInTheDocument();
  });

  it("shows what republishing would change, and what an earlier version left behind", async () => {
    const onPublish = vi.fn();
    const republish: PublicationPreview = {
      ...preview,
      status: "outdated",
      published_revision: 2,
      items: [
        { ...epic, action: "unchanged", external_id: "41", url: "https://dev.azure.com/contoso/41" },
        { ...feature, action: "update", external_id: "42", url: "https://dev.azure.com/contoso/42" },
        { ...story, action: "create" },
      ],
      removed: [
        { local_key: "s-old", kind: "story", external_id: "43", url: "https://dev.azure.com/contoso/43", revision: 2, published_at: "2026-10-09T09:00:00Z" },
      ],
    };
    render(<PublicationPanel {...base} preview={republish} onPublish={onPublish} />);

    expect(screen.getByText("Outdated")).toBeInTheDocument();
    expect(screen.getByText("Version 2 is in the tracker; this version is not yet.")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Work items for version 3" });
    expect(within(table).getByText("Unchanged")).toBeInTheDocument();
    expect(within(table).getByText("Changed")).toBeInTheDocument();
    expect(within(table).getByText("New")).toBeInTheDocument();
    expect(within(table).getByRole("link", { name: /Open item 42/ })).toHaveAttribute("href", "https://dev.azure.com/contoso/42");
    const removed = screen.getByRole("region", { name: "No longer in version 3" });
    expect(within(removed).getByRole("link", { name: /Open item 43/ })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Publish changes" }));
    const dialog = screen.getByRole("dialog", { name: "Publish version 3?" });
    expect(within(dialog).getByText(/creates 1 and updates 1 work items/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));
    expect(onPublish).toHaveBeenCalledWith("fp-3");
  });

  it("offers nothing to send when the tracker already matches", () => {
    const current: PublicationPreview = {
      ...preview,
      status: "published",
      published_revision: 3,
      items: preview.items.map((item, index) => ({ ...item, action: "unchanged", external_id: String(41 + index), url: `https://dev.azure.com/contoso/${41 + index}` })),
    };
    render(<PublicationPanel {...base} preview={current} onPublish={vi.fn()} />);

    expect(screen.queryByRole("button", { name: /Publish/ })).not.toBeInTheDocument();
    expect(screen.getByText("Azure DevOps already matches version 3; there is nothing to send.")).toBeInTheDocument();
  });

  it("offers a retry when this version's last attempt did not finish", async () => {
    const onRetry = vi.fn();
    const attempt: PublicationStatus["attempts"][number] = {
      number: 1,
      revision: 3,
      actor_name: "Dana Owner",
      started_at: "2026-10-10T09:00:00Z",
      finished_at: "2026-10-10T09:01:00Z",
      outcome: "partial",
      items: [],
    };
    const status: PublicationStatus = {
      requirement_id: "r-1",
      status: "incomplete",
      latest_approved_revision: 3,
      published_revision: null,
      product_verdict: null,
      product_impact_version: null,
      mappings: [],
      attempts: [attempt],
    };
    render(<PublicationPanel {...base} preview={{ ...preview, status: "incomplete" }} status={status} onRetry={onRetry} onPublish={vi.fn()} />);

    expect(screen.getByText("The last attempt by Dana Owner did not send every item.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();

    render(
      <PublicationPanel
        {...base}
        preview={{ ...preview, status: "incomplete" }}
        status={{ ...status, attempts: [{ ...attempt, revision: 2 }] }}
        onRetry={onRetry}
        onPublish={vi.fn()}
      />,
    );
    expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(1);
  });
});
