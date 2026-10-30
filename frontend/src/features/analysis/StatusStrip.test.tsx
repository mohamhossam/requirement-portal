import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { RequirementAnalysis } from "../../api/client";
import { analysisFixture } from "../../test/fixtures";
import { StatusStrip, type SpecificationDownload } from "./StatusStrip";

const confirmed: RequirementAnalysis = {
  ...analysisFixture,
  human_confirmed: true,
  confirmed_at: "2026-09-05T12:05:00Z",
  confirmed_by: { id: "owner-1", display_name: "Olivia Owner", email: null },
};

function specification(overrides: Partial<SpecificationDownload> = {}): SpecificationDownload {
  return { revision: 4, busy: false, error: null, downloaded: null, onDownload: vi.fn(), ...overrides };
}

describe("StatusStrip", () => {
  it("offers the Business Requirements Document only once the analysis is confirmed", () => {
    const { rerender } = render(<StatusStrip analysis={analysisFixture} answered={1} open={1} specification={specification()} />);
    expect(screen.queryByRole("group", { name: "Business Requirements Document" })).not.toBeInTheDocument();

    rerender(<StatusStrip analysis={confirmed} answered={2} open={0} specification={null} />);
    expect(screen.getByText("Confirmed by a person")).toBeVisible();
    expect(screen.queryByRole("group", { name: "Business Requirements Document" })).not.toBeInTheDocument();

    rerender(<StatusStrip analysis={confirmed} answered={2} open={0} specification={specification()} />);
    expect(screen.getByRole("group", { name: "Business Requirements Document" })).toBeVisible();
    expect(screen.getByText("Business Requirements Document, version 4")).toBeVisible();
  });

  it("downloads Word or Markdown and says what was downloaded", async () => {
    const download = specification();
    const { rerender } = render(<StatusStrip analysis={confirmed} answered={2} open={0} specification={download} />);

    await userEvent.click(screen.getByRole("button", { name: "Download Word document" }));
    expect(download.onDownload).toHaveBeenCalledWith("docx");
    await userEvent.click(screen.getByRole("button", { name: "Download Markdown" }));
    expect(download.onDownload).toHaveBeenCalledWith("md");

    rerender(<StatusStrip analysis={confirmed} answered={2} open={0} specification={specification({ downloaded: "docx" })} />);
    expect(screen.getByRole("status")).toHaveTextContent("Downloaded version 4 as Word document.");
  });

  it("keeps the button focusable while the file is prepared, ignores a second press, and reports a failure", async () => {
    const busy = specification({ busy: true });
    const { rerender } = render(<StatusStrip analysis={confirmed} answered={2} open={0} specification={busy} />);
    const button = screen.getByRole("button", { name: "Preparing the document…" });
    expect(button).toBeEnabled();
    await userEvent.click(button);
    await userEvent.click(screen.getByRole("button", { name: "Download Markdown" }));
    expect(busy.onDownload).not.toHaveBeenCalled();

    rerender(<StatusStrip analysis={confirmed} answered={2} open={0} specification={specification({ error: "The document could not be prepared." })} />);
    expect(screen.getByRole("alert")).toHaveTextContent("The document could not be prepared.");
  });
});
