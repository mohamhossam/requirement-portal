import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RequirementForm } from "./RequirementForm";

describe("RequirementForm", () => {
  it("blocks blank input", async () => {
    const onSubmit = vi.fn();
    render(<RequirementForm submitLabel="Create requirement" onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: "Create requirement" }));
    expect(screen.getAllByText("Add a short title for this requirement.")).toHaveLength(2);
    expect(screen.getAllByText("Describe the business need before continuing.")).toHaveLength(2);
    expect(screen.getByRole("group", { name: "Check the requirement details" })).toHaveFocus();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("provides intake guidance and submits trimmed source text", async () => {
    const onSubmit = vi.fn();
    render(
      <RequirementForm
        context="create"
        submitLabel="Save and open review"
        onSubmit={onSubmit}
      />,
    );

    const title = screen.getByLabelText(/Requirement title/);
    expect(title).toHaveFocus();
    expect(title).toHaveAccessibleDescription(
      "A short name people will recognise, like “High-speed business bundles”.",
    );

    await userEvent.type(title, "  High-speed bundles  ");
    await userEvent.type(
      screen.getByLabelText(/Business need/),
      "  Make eligible XGPON bundles orderable.  ",
    );
    // The optional detail starts closed on a blank draft, and opens on request.
    await userEvent.click(screen.getByText("Add detail if you know it (optional)"));
    await userEvent.type(screen.getByLabelText(/Desired outcome/), "  Customers can order.  ");
    await userEvent.click(screen.getByRole("button", { name: "Save and open review" }));

    expect(onSubmit).toHaveBeenCalledWith(
      {
        title: "High-speed bundles",
        description: "Make eligible XGPON bundles orderable.",
        desired_outcome: "Customers can order.",
        customer_context: "",
        channels: [],
        systems: [],
        business_rules: [],
        constraints: [],
      },
      "primary",
    );
  });

  it("renders a server validation error", () => {
    render(<RequirementForm submitLabel="Save requirement" error="title: Field required" onSubmit={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("title: Field required");
  });

  it("opens the optional detail when a draft already carries some", () => {
    render(<RequirementForm context="create" submitLabel="Save" onSubmit={vi.fn()} initial={{ title: "T", description: "D", systems: ["BCRM"] }} />);
    expect(screen.getByLabelText(/Systems involved/)).toBeVisible();
    expect(screen.getByLabelText(/Systems involved/)).toHaveValue("BCRM");
  });

  it("drops the business need requirement once a ready file carries it", () => {
    render(<RequirementForm context="create" submitLabel="Save" onSubmit={vi.fn()} hasIncludedAttachment attachments={<p>files</p>} />);
    expect(screen.getByLabelText(/Business need/)).not.toBeRequired();
    expect(screen.getByLabelText(/Requirement title/)).toBeRequired();
  });
});
