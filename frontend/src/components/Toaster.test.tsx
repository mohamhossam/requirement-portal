import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { Toaster } from "./Toaster";
import { useToast, type ToastInput } from "./useToast";

function Publisher({ toasts }: { toasts: ToastInput[] }) {
  const toast = useToast();
  return (
    <>
      {toasts.map((input, index) => (
        <button key={index} type="button" onClick={() => toast.show(input)}>
          publish {index}
        </button>
      ))}
    </>
  );
}

function mount(toasts: ToastInput[]) {
  return render(
    <MemoryRouter initialEntries={["/here"]}>
      <Toaster>
        <Routes>
          <Route path="/here" element={<Publisher toasts={toasts} />} />
          <Route path="/there" element={<h1>Arrived</h1>} />
        </Routes>
      </Toaster>
    </MemoryRouter>,
  );
}

const publish = (index = 0) =>
  userEvent.click(screen.getByRole("button", { name: `publish ${index}` }));

describe("Toaster", () => {
  it("announces a notice politely", async () => {
    mount([{ tone: "success", title: "Epic generation finished" }]);
    await publish();
    const notice = await screen.findByText("Epic generation finished");
    // role="status" carries aria-live="polite" implicitly. The politeness is on
    // the toast rather than on the stack around it, so the two tones can differ.
    expect(notice.closest("[role]")).toHaveAttribute("role", "status");
  });

  it("interrupts for a failure", async () => {
    mount([{ tone: "error", title: "Analysis failed", message: "The model timed out." }]);
    await publish();
    const notice = await screen.findByText("Analysis failed");
    // Politely queued, a failure waits for whatever is already being read and
    // can be dropped altogether — on the one message the person must not miss.
    expect(notice.closest("[role]")).toHaveAttribute("role", "alert");
  });

  it("can be dismissed by hand", async () => {
    mount([{ tone: "error", title: "Analysis failed", message: "The model timed out." }]);
    await publish();
    await screen.findByText("Analysis failed");
    await userEvent.click(screen.getByRole("button", { name: "Dismiss: Analysis failed" }));
    expect(screen.queryByText("Analysis failed")).not.toBeInTheDocument();
  });

  it("keeps failures on screen and lets successes go by themselves", async () => {
    mount([
      { tone: "error", title: "Analysis failed" },
      { tone: "success", title: "Epic generation finished" },
    ]);
    await publish(0);
    await publish(1);
    await waitFor(
      () => expect(screen.queryByText("Epic generation finished")).not.toBeInTheDocument(),
      { timeout: 8_000 },
    );
    expect(screen.getByText("Analysis failed")).toBeInTheDocument();
  }, 10_000);

  it("replaces a keyed notice instead of stacking repeats", async () => {
    mount([
      { tone: "error", title: "Epic generation failed", key: "job-generate_epic" },
      { tone: "success", title: "Epic generation finished", key: "job-generate_epic" },
    ]);
    await publish(0);
    await publish(1);
    expect(screen.queryByText("Epic generation failed")).not.toBeInTheDocument();
    expect(screen.getByText("Epic generation finished")).toBeInTheDocument();
  });

  it("offers a link to the result and closes once it is followed", async () => {
    mount([{ tone: "success", title: "Features ready", to: "/there", linkLabel: "Open result" }]);
    await publish();
    await userEvent.click(await screen.findByRole("link", { name: "Open result" }));
    expect(await screen.findByRole("heading", { name: "Arrived" })).toBeInTheDocument();
    expect(screen.queryByText("Features ready")).not.toBeInTheDocument();
  });

  it("shows nothing at all until something is published", () => {
    mount([{ tone: "info", title: "Quiet" }]);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
