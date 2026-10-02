import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef, useState } from "react";
import { describe, expect, it } from "vitest";

import { Modal } from "./Modal";

/**
 * Focus trapping is not asserted here. The trap skips controls with no layout
 * boxes, and jsdom gives every element an empty getClientRects(), so it is
 * inert in this environment by design. Real browsers trap natively through the
 * top layer, and tests/analysis-sources.spec.ts and tests/focused-breakdown.spec.ts
 * assert the wrap there.
 */

function Host({ label, portal = false }: { label?: string; portal?: boolean }) {
  const [open, setOpen] = useState(false);
  const confirmRef = useRef<HTMLButtonElement>(null);
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>Open</button>
      {open && (
        <Modal
          className="confirm-dialog"
          label={label ?? "Test dialog"}
          onClose={() => setOpen(false)}
          initialFocus={confirmRef}
          portal={portal}
        >
          <button type="button">Cancel</button>
          <button ref={confirmRef} type="button">Confirm</button>
        </Modal>
      )}
    </div>
  );
}

const open = () => userEvent.click(screen.getByRole("button", { name: "Open" }));

describe("Modal", () => {
  it("opens as a named dialog", async () => {
    render(<Host />);
    await open();
    expect(screen.getByRole("dialog", { name: "Test dialog" })).toBeInTheDocument();
  });

  it("focuses what the caller asked for rather than the first control", async () => {
    render(<Host />);
    await open();
    expect(screen.getByRole("button", { name: "Confirm" })).toHaveFocus();
  });

  it("closes on Escape", async () => {
    render(<Host />);
    await open();
    fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: true, cancelable: true }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("returns focus to whatever opened it", async () => {
    render(<Host />);
    const opener = screen.getByRole("button", { name: "Open" });
    await open();
    fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: true, cancelable: true }));
    expect(opener).toHaveFocus();
  });

  it("closes on a click outside its box but not on one inside", async () => {
    render(<Host />);
    await open();
    const dialog = screen.getByRole("dialog");

    // jsdom reports a zero-sized box, so any positive coordinate is outside it.
    fireEvent.click(dialog, { clientX: 0, clientY: 0 });
    expect(screen.queryByRole("dialog")).toBeInTheDocument();

    fireEvent.click(dialog, { clientX: 500, clientY: 500 });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("ignores clicks on its own contents", async () => {
    render(<Host />);
    await open();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("renders in place by default, and into the body when asked", async () => {
    const { container, unmount } = render(<Host />);
    await open();
    expect(container.querySelector("dialog")).toBeInTheDocument();
    unmount();

    const portaled = render(<Host portal />);
    await open();
    // Escaping the tree is what lets the drawer avoid `.breakdown-shell .button`.
    expect(portaled.container.querySelector("dialog")).toBeNull();
    expect(document.body.querySelector("dialog")).toBeInTheDocument();
  });
});
