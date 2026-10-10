import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { expect, it } from "vitest";

import { renderWithClient } from "../../test/renderWithClient";
import { AppShell } from "./AppShell";

function Tree() {
  const navigate = useNavigate();
  return (
    <div>
      <button type="button" onClick={() => navigate("/tree/a")}>Feature A</button>
      <button type="button" onClick={() => navigate("/tree/b")}>Feature B</button>
      <button type="button" onClick={() => navigate("/tree/b?filter=open")}>Open only</button>
    </div>
  );
}

function renderShell(path = "/") {
  renderWithClient(
    <MemoryRouter initialEntries={[path]}>
      <AppShell>
        <Routes>
          <Route path="/" element={<Link to="/reports">Reports</Link>} />
          <Route path="/reports" element={<h1>Reports page</h1>} />
          <Route path="/tree/*" element={<Tree />} />
        </Routes>
      </AppShell>
    </MemoryRouter>,
  );
  return screen.getByRole("main");
}

it("is reachable by the skip link and the route change, but is never a Tab stop", () => {
  const main = renderShell();
  expect(main).toHaveAttribute("id", "main-content");
  expect(main).toHaveAttribute("tabindex", "-1");
  // The first render is not a navigation: focus is left where the browser put it.
  expect(main).not.toHaveFocus();
});

it("moves focus to the new page's content when the page changes", async () => {
  const main = renderShell();
  // A link inside the page, which the navigation then removes.
  await userEvent.click(within(main).getByRole("link", { name: "Reports" }));

  expect(await screen.findByRole("heading", { name: "Reports page" })).toBeVisible();
  expect(main).toHaveFocus();
});

it("moves focus from the navigation to the page it opened", async () => {
  const main = renderShell("/tree/a");
  const navigation = screen.getByRole("navigation", { name: "Global" });
  await userEvent.click(within(navigation).getByRole("link", { name: "Reports" }));

  expect(await screen.findByRole("heading", { name: "Reports page" })).toBeVisible();
  expect(main).toHaveFocus();
});

it("leaves focus where it is when the address changes inside the same page", async () => {
  renderShell("/tree/a");
  const featureB = screen.getByRole("button", { name: "Feature B" });

  await userEvent.click(featureB);
  expect(featureB).toHaveFocus();

  const filter = screen.getByRole("button", { name: "Open only" });
  await userEvent.click(filter);
  expect(filter).toHaveFocus();
});
