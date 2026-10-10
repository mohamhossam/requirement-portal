import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { reportClientError } from "../../api/clientErrors";
import { ErrorBoundary } from "./ErrorBoundary";

vi.mock("../../api/clientErrors", () => ({ reportClientError: vi.fn() }));

let failure: Error | null = null;

function Page() {
  if (failure) throw failure;
  return <p>Worklist</p>;
}

beforeEach(() => {
  failure = null;
  vi.spyOn(console, "error").mockImplementation(() => undefined);
});
afterEach(() => vi.restoreAllMocks());

it("shows a way out instead of a blank page, and recovers when tried again", async () => {
  failure = new TypeError("Cannot read properties of undefined");
  render(<ErrorBoundary scope="route"><Page /></ErrorBoundary>);

  expect(screen.getByRole("heading", { name: "This page stopped working", level: 2 })).toBeVisible();
  expect(screen.getByRole("button", { name: "Reload the page" })).toBeVisible();
  // Operators hear of it too, as the kind of failure only.
  expect(reportClientError).toHaveBeenCalledWith("render");

  failure = null;
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(screen.getByText("Worklist")).toBeVisible();
});

it("asks for a reload when a redeploy removed the page's code", async () => {
  const reload = vi.fn();
  vi.spyOn(window, "location", "get").mockReturnValue({ ...window.location, reload });
  failure = new TypeError("Failed to fetch dynamically imported module: /assets/ReportsPage-1a2b.js");
  render(<ErrorBoundary scope="page"><Page /></ErrorBoundary>);

  expect(screen.getByRole("main")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "A new version is available", level: 1 })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  expect(reportClientError).toHaveBeenCalledWith("chunk_load");
  await userEvent.click(screen.getByRole("button", { name: "Reload the page" }));
  expect(reload).toHaveBeenCalledOnce();
});

it("leaves a crash behind when the person navigates elsewhere", () => {
  failure = new Error("broken");
  const { rerender } = render(<ErrorBoundary scope="route" resetKey="/reports"><Page /></ErrorBoundary>);
  expect(screen.getByRole("alert")).toBeVisible();

  failure = null;
  rerender(<ErrorBoundary scope="route" resetKey="/activity"><Page /></ErrorBoundary>);
  expect(screen.getByText("Worklist")).toBeVisible();
});
