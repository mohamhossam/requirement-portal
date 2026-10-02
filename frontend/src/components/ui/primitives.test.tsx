import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { Badge, Pill } from "./Badge";
import { Button } from "./Button";
import { Card } from "./Card";
import { Checkbox } from "./Checkbox";
import { Input } from "./Input";
import { Select } from "./Select";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "./Table";
import { Tab, TabList, TabPanel, Tabs } from "./Tabs";

/**
 * These cover the promises the primitives make on every screen's behalf, and
 * only those: the wiring a screen would otherwise have to remember — a label
 * that points at its field, an error that is announced rather than merely
 * reddened, a sort direction that exists for a screen reader, a target that
 * clears 24×24. The paint is not asserted; a class name is not a behaviour.
 */
describe("Button", () => {
  it("disables for the duration of an async action and says what is running", async () => {
    const onClick = vi.fn();
    render(
      <Button loading loadingLabel="Analysing…" onClick={onClick} variant="primary">
        Save and analyse
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Analysing…" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("keeps a gated action visible and explains why", async () => {
    const onClick = vi.fn();
    render(
      <Button blockedReason="Answer 4 blocking questions first" onClick={onClick} variant="primary">
        Confirm breakdown
      </Button>,
    );
    const button = screen.getByRole("button", { name: /Confirm breakdown/ });
    // Not `disabled`: it keeps its place in the tab order, and the reason is
    // part of its accessible description rather than a tooltip nobody reaches.
    expect(button).not.toBeDisabled();
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAccessibleDescription("Answer 4 blocking questions first");
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("Input", () => {
  it("labels the field and describes it with the hint and then the error", () => {
    render(
      <Input
        error="Give the business need in at least one sentence."
        hint="Example: High-speed business bundles"
        label="Business need"
      />,
    );
    const field = screen.getByLabelText("Business need");
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription(
      "Example: High-speed business bundles Give the business need in at least one sentence.",
    );
    // Beside the problem, and announced — not only painted red (§4.5, §13.6).
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Give the business need in at least one sentence.",
    );
  });

  it("marks a required field for both channels", () => {
    render(<Input label="Title" required />);
    expect(screen.getByLabelText(/Title/)).toBeRequired();
    expect(screen.getByText("(required)")).toBeInTheDocument();
  });
});

describe("Select", () => {
  it("disables and announces while its options are loading", () => {
    render(
      <Select label="Owner" loading loadingLabel="Loading owners…">
        <option value="">Unassigned</option>
      </Select>,
    );
    const field = screen.getByLabelText("Owner");
    expect(field).toBeDisabled();
    expect(field).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("status")).toHaveTextContent("Loading owners…");
  });
});

describe("Checkbox", () => {
  it("toggles from its label and carries the indeterminate DOM property", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<Checkbox label="Select all rows" onChange={onChange} />);
    const box = screen.getByRole("checkbox", { name: /Select all rows/ });
    await userEvent.click(screen.getByText("Select all rows"));
    expect(onChange).toHaveBeenCalled();

    rerender(<Checkbox indeterminate label="Select all rows" onChange={onChange} />);
    // An HTML attribute does not exist for this; it is a DOM property only.
    expect((box as HTMLInputElement).indeterminate).toBe(true);
  });

  it("links its error to the box", () => {
    render(<Checkbox error="Approval requires a reviewer." label="Approved" />);
    expect(screen.getByRole("checkbox", { name: /Approved/ })).toHaveAccessibleDescription(
      "Approval requires a reviewer.",
    );
  });
});

describe("Table", () => {
  function Rows({ onSort }: { onSort: () => void }) {
    return (
      <Table caption="Requirements worklist">
        <TableHead>
          <TableRow>
            <TableHeaderCell onSort={onSort} sort="asc">
              Requirement
            </TableHeaderCell>
            <TableHeaderCell>Owner</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody columns={2}>
          <TableRow>
            <TableCell>XGPON qualification</TableCell>
            <TableCell>Unassigned</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    );
  }

  it("exposes the sort direction on the column, not on the button", async () => {
    const onSort = vi.fn();
    render(<Rows onSort={onSort} />);
    const header = screen.getByRole("columnheader", { name: /Requirement/ });
    expect(header).toHaveAttribute("aria-sort", "ascending");
    expect(screen.getByRole("columnheader", { name: "Owner" })).not.toHaveAttribute("aria-sort");
    await userEvent.click(within(header).getByRole("button"));
    expect(onSort).toHaveBeenCalledOnce();
  });

  it("swaps the body for its loading, error and empty states while the header stays", () => {
    const { rerender } = render(
      <Table caption="Requirements">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Requirement</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody columns={1} loading loadingLabel="Loading requirements…" />
      </Table>,
    );
    expect(screen.getByRole("status", { name: "Loading requirements…" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader")).toBeInTheDocument();

    rerender(
      <Table caption="Requirements">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Requirement</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody columns={1} error="The worklist could not be loaded." />
      </Table>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("The worklist could not be loaded.");

    rerender(
      <Table caption="Requirements">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Requirement</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody columns={1} empty="Nothing is waiting on you." />
      </Table>,
    );
    expect(screen.getByText("Nothing is waiting on you.")).toBeInTheDocument();
  });
});

describe("Tabs", () => {
  function Sections() {
    return (
      <Tabs defaultValue="findings">
        <TabList label="Requirement sections">
          <Tab count={4} value="findings">
            Findings
          </Tab>
          <Tab value="backlog">Backlog</Tab>
          <Tab disabled value="approval">
            Approval
          </Tab>
        </TabList>
        <TabPanel value="findings">Four blocking questions</TabPanel>
        <TabPanel value="backlog">Two epics</TabPanel>
        <TabPanel value="approval">Not yet</TabPanel>
      </Tabs>
    );
  }

  it("is one tab stop, and the arrow keys move between tabs", async () => {
    render(<Sections />);
    const findings = screen.getByRole("tab", { name: /Findings/ });
    expect(findings).toHaveAttribute("aria-selected", "true");
    expect(findings).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: "Backlog" })).toHaveAttribute("tabindex", "-1");

    findings.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Backlog" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Two epics");
  });

  it("skips a tab that cannot be opened without hiding it", async () => {
    render(<Sections />);
    const approval = screen.getByRole("tab", { name: "Approval" });
    expect(approval).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(approval);
    expect(approval).toHaveAttribute("aria-selected", "false");

    // From Backlog, ArrowRight wraps past the disabled tab to the first one.
    screen.getByRole("tab", { name: "Backlog" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: /Findings/ })).toHaveAttribute("aria-selected", "true");
  });

  it("ties each panel to the tab that opened it", () => {
    render(<Sections />);
    expect(screen.getByRole("tabpanel")).toHaveAccessibleName(/Findings/);
  });
});

describe("Badge and Pill", () => {
  it("never lets colour be the only channel", () => {
    const { container } = render(<Badge tone="danger">Blocks confirmation</Badge>);
    expect(screen.getByText("Blocks confirmation")).toBeInTheDocument();
    // The glyph is decorative and unremovable: the text is the second channel
    // for assistive technology, the shape is the second channel for everyone
    // who can see the badge but not the hue (§4.5).
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("says whether a filter is applied", async () => {
    const onClick = vi.fn();
    render(
      <MemoryRouter>
        <Pill active count={3} onClick={onClick}>
          Blocking
        </Pill>
      </MemoryRouter>,
    );
    expect(screen.getByRole("button", { pressed: true })).toHaveTextContent("Blocking");
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });
});

describe("Card", () => {
  it("reserves the space it will fill, then reports a failure in place", () => {
    const { rerender } = render(
      <Card loading loadingLabel="Loading the analysis…">
        <p>Findings</p>
      </Card>,
    );
    expect(screen.getByRole("status", { name: "Loading the analysis…" })).toBeInTheDocument();
    expect(screen.queryByText("Findings")).not.toBeInTheDocument();

    rerender(
      <Card error="The analysis could not be loaded.">
        <p>Findings</p>
      </Card>,
    );
    // In place, beside the thing that failed — never only in a toast (§16).
    expect(screen.getByRole("alert")).toHaveTextContent("The analysis could not be loaded.");
  });
});
