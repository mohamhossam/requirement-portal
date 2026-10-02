import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { UnsavedChangesProvider } from "./UnsavedChangesProvider";
import { useUnsavedGuard } from "./useUnsavedChanges";

function Editor({ enabled = true }: { enabled?: boolean }) {
  const [text, setText] = useState("original");
  useUnsavedGuard({ text }, enabled);
  return (
    <>
      <label>
        Epic name
        <input value={text} onChange={(event) => setText(event.target.value)} />
      </label>
      <Link to="/elsewhere">Go elsewhere</Link>
      <a href="/elsewhere" download="export.json">Download</a>
      <a href="https://example.com/docs">External docs</a>
    </>
  );
}

function renderApp(enabled = true) {
  return render(
    <MemoryRouter initialEntries={["/editor"]}>
      <UnsavedChangesProvider>
        <Routes>
          <Route path="/editor" element={<Editor enabled={enabled} />} />
          <Route path="/elsewhere" element={<h1>Elsewhere</h1>} />
        </Routes>
      </UnsavedChangesProvider>
    </MemoryRouter>,
  );
}

const dirty = () => userEvent.type(screen.getByLabelText("Epic name"), " changed");
const leave = () => userEvent.click(screen.getByRole("link", { name: "Go elsewhere" }));
const prompt = () => screen.queryByRole("heading", { name: "Leave without saving?" });

describe("unsaved changes guard", () => {
  it("lets a clean editor navigate away without prompting", async () => {
    renderApp();
    await leave();
    expect(await screen.findByRole("heading", { name: "Elsewhere" })).toBeInTheDocument();
    expect(prompt()).not.toBeInTheDocument();
  });

  it("blocks in-app navigation once the editor is dirty", async () => {
    renderApp();
    await dirty();
    await leave();
    expect(prompt()).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Elsewhere" })).not.toBeInTheDocument();
  });

  it("stays put when the person cancels", async () => {
    renderApp();
    await dirty();
    await leave();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(prompt()).not.toBeInTheDocument();
    expect(screen.getByLabelText("Epic name")).toHaveValue("original changed");
  });

  it("completes the navigation when the person discards", async () => {
    renderApp();
    await dirty();
    await leave();
    await userEvent.click(screen.getByRole("button", { name: "Discard changes and leave" }));
    expect(await screen.findByRole("heading", { name: "Elsewhere" })).toBeInTheDocument();
  });

  it("stops prompting when the edit is reverted by hand", async () => {
    renderApp();
    await dirty();
    await userEvent.clear(screen.getByLabelText("Epic name"));
    await userEvent.type(screen.getByLabelText("Epic name"), "original");
    await leave();
    expect(await screen.findByRole("heading", { name: "Elsewhere" })).toBeInTheDocument();
  });

  it("does not guard an editor that opts out, such as the autosaving draft", async () => {
    renderApp(false);
    await dirty();
    await leave();
    expect(await screen.findByRole("heading", { name: "Elsewhere" })).toBeInTheDocument();
  });

  it("ignores downloads and links that leave the application", async () => {
    renderApp();
    await dirty();
    await userEvent.click(screen.getByRole("link", { name: "Download" }));
    expect(prompt()).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "External docs" }));
    expect(prompt()).not.toBeInTheDocument();
  });

  it("warns the browser before unload only while dirty", async () => {
    renderApp();

    const clean = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(clean);
    expect(clean.defaultPrevented).toBe(false);

    await dirty();
    const pending = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(pending);
    expect(pending.defaultPrevented).toBe(true);
  });
});

describe("navigation that keeps editors mounted", () => {
  function renderWorkspace() {
    return render(
      <MemoryRouter initialEntries={["/requirements/req-1/breakdown/epic"]}>
        <UnsavedChangesProvider>
          <Routes>
            <Route path="/requirements/:id/breakdown/*" element={<>
              <Editor />
              <Link to="/requirements/req-1/breakdown/features/feature-1">Sibling item</Link>
              <Link to="/requirements/req-1/capture">Another stage</Link>
              <Link to="/requirements/req-2/breakdown/epic">Another requirement</Link>
            </>} />
            <Route path="/requirements/:id/capture" element={<h1>Capture</h1>} />
            <Route path="/requirements/req-2/breakdown/epic" element={<h1>Other requirement</h1>} />
          </Routes>
        </UnsavedChangesProvider>
      </MemoryRouter>,
    );
  }

  it("does not warn when moving between backlog items, where ADR-0045 keeps the draft", async () => {
    renderWorkspace();
    await dirty();
    await userEvent.click(screen.getByRole("link", { name: "Sibling item" }));
    expect(prompt()).not.toBeInTheDocument();
    expect(screen.getByLabelText("Epic name")).toHaveValue("original changed");
  });

  it("warns when leaving the workspace for another stage, which unmounts it", async () => {
    renderWorkspace();
    await dirty();
    await userEvent.click(screen.getByRole("link", { name: "Another stage" }));
    expect(prompt()).toBeInTheDocument();
  });

  it("warns when switching to a different requirement's workspace", async () => {
    renderWorkspace();
    await dirty();
    await userEvent.click(screen.getByRole("link", { name: "Another requirement" }));
    expect(prompt()).toBeInTheDocument();
  });
});
