import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { HelpMenu } from "./HelpMenu";

async function exampleLink(path: string) {
  render(<MemoryRouter initialEntries={[path]}><HelpMenu /></MemoryRouter>);
  await userEvent.click(screen.getByRole("button", { name: /help/i }));
  return screen.getByRole("link", { name: "Read the worked example" });
}

describe("HelpMenu", () => {
  it("links to the worked example on the intake page", async () => {
    expect(await exampleLink("/")).toHaveAttribute("href", "/requirements/new#example");
  });

  it("keeps an open draft when the owner is already on the intake page", async () => {
    // A bare /requirements/new#example opened a blank form over the owner's work.
    expect(await exampleLink("/requirements/new?draft=draft-1"))
      .toHaveAttribute("href", "/requirements/new?draft=draft-1#example");
  });
});
