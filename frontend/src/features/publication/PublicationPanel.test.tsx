import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { PublicationPreview, PublicationReport } from "../../api/client";
import { PublicationPanel } from "./PublicationPanel";

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
  items: [
    { key: "e", kind: "epic", label: "Epic", title: "Online ordering", parent_key: null, acceptance_criteria_count: 0, owning_squad_name: null, location: "SMB" },
    { key: "f", kind: "feature", label: "Feature 1", title: "Order a line", parent_key: "e", acceptance_criteria_count: 0, owning_squad_name: "Billing", location: "SMB\\Billing" },
    { key: "s", kind: "story", label: "Story 1.1", title: "As a customer, I want to order", parent_key: "f", acceptance_criteria_count: 2, owning_squad_name: "Billing", location: "SMB\\Billing" },
  ],
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
        { key: "e", kind: "epic", label: "Epic", title: "Online ordering", status: "published", external_id: "41", url: "https://dev.azure.com/contoso/41", error: null },
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
});
