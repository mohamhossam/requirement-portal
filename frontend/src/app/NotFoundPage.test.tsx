import { screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";

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
