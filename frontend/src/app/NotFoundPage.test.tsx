import { screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { api } from "../api/client";

import { renderWithClient } from "../test/renderWithClient";
import { App } from "./App";

it("says an unknown address is not a page, with one way back", async () => {
  renderWithClient(
    <MemoryRouter initialEntries={["/requirments/typo"]}>
      <App />
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { level: 1, name: "Page not found" })).toBeVisible();
  expect(screen.getByRole("heading", { level: 2, name: "There is nothing at this address" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Go to the dashboard" })).toHaveAttribute("href", "/");
  expect(document.title).toBe("Page not found · Requirement AI");
});

it("keeps the sign-in callback path on the dashboard, not the not-found page", async () => {
  const pending = () => new Promise<never>(() => undefined);
  vi.spyOn(api, "listRequirements").mockImplementation(pending);
  vi.spyOn(api, "listRequirementDrafts").mockImplementation(pending);
  vi.spyOn(api, "listSavedViews").mockImplementation(pending);
  renderWithClient(
    <MemoryRouter initialEntries={["/auth/callback"]}>
      <App />
    </MemoryRouter>,
  );

  expect(await screen.findByRole("heading", { level: 1 })).not.toHaveTextContent("Page not found");
  expect(screen.queryByRole("heading", { name: "Page not found" })).toBeNull();
});
