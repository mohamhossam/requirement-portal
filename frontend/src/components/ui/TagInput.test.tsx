import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { TagInput } from "./TagInput";

/** The caller-owned state exactly as a form holds it. */
function Harness({ initial = [] as string[] }) {
  const [values, setValues] = useState<string[]>(initial);
  const [draft, setDraft] = useState("");
  return (
    <TagInput
      label="Other names"
      values={values}
      onChange={setValues}
      draft={draft}
      onDraftChange={setDraft}
    />
  );
}

const chips = () => screen.queryAllByRole("listitem").map((item) => item.textContent);

describe("TagInput", () => {
  it("commits a chip on Enter and on comma, never submitting the draft twice", async () => {
    render(<Harness />);
    const field = screen.getByLabelText("Other names");
    await userEvent.type(field, "GPON{Enter}");
    await userEvent.type(field, "fibre,");
    expect(chips()).toEqual(["GPON", "fibre"]);
    expect(field).toHaveValue("");
  });

  it("splits a pasted list into chips", async () => {
    render(<Harness />);
    const field = screen.getByLabelText("Other names");
    await userEvent.click(field);
    await userEvent.paste("alpha, beta\ngamma");
    expect(chips()).toEqual(["alpha", "beta", "gamma"]);
  });

  it("takes the last chip back into the field on Backspace over an empty draft", async () => {
    render(<Harness initial={["alpha", "beta"]} />);
    const field = screen.getByLabelText("Other names");
    await userEvent.click(field);
    await userEvent.keyboard("{Backspace}");
    expect(chips()).toEqual(["alpha"]);
    expect(field).toHaveValue("beta");
    expect(screen.getByRole("status")).toHaveTextContent("beta is back in the field to edit.");
  });

  it("removes one chip, announces it, and moves focus to the chip that took its place", async () => {
    render(<Harness initial={["alpha", "beta", "gamma"]} />);
    await userEvent.click(screen.getByRole("button", { name: "Remove beta" }));
    expect(chips()).toEqual(["alpha", "gamma"]);
    expect(screen.getByRole("status")).toHaveTextContent("Removed beta.");
    expect(screen.getByRole("button", { name: "Remove gamma" })).toHaveFocus();
  });

  it("returns focus to the field when the last chip goes", async () => {
    render(<Harness initial={["alpha"]} />);
    await userEvent.click(screen.getByRole("button", { name: "Remove alpha" }));
    expect(chips()).toEqual([]);
    expect(screen.getByLabelText("Other names")).toHaveFocus();
  });

  it("commits the draft on blur so an unsubmitted entry is not lost", async () => {
    render(<Harness />);
    const field = screen.getByLabelText("Other names");
    await userEvent.type(field, "left behind");
    await userEvent.tab();
    expect(chips()).toEqual(["left behind"]);
  });
});
