import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { knowledgeApi, type ActiveRelease } from "../../api/knowledge";
import { renderWithClient } from "../../test/renderWithClient";
import { ArchitectureRemapBanner } from "./ArchitectureRemapBanner";

// The version in use, as this app's copy of the knowledge portal's activations names it.
const inUse: ActiveRelease = { id: "rel-2", name: "October integration update" };

afterEach(() => vi.restoreAllMocks());

it("offers the team a confirmed remap when the breakdown uses an older version", async () => {
  vi.spyOn(knowledgeApi, "activeRelease").mockResolvedValue(inUse);
  const remap = vi.fn();

  renderWithClient(<ArchitectureRemapBanner mappedWith={["rel-1", "rel-1"]} canRemap busy={false} onRemap={remap} />);

  expect(await screen.findByRole("heading", { name: "Mapped with an older architecture catalogue" })).toBeVisible();
  expect(screen.getByText(/“October integration update”, is in use/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Remap architecture" }));
  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByText(/Approvals on this breakdown are reset/)).toBeVisible();
  await userEvent.click(within(dialog).getByRole("button", { name: "Remap" }));
  expect(remap).toHaveBeenCalledOnce();
});

it("stays quiet when the mapping is current, or unmapped", async () => {
  const active = vi.spyOn(knowledgeApi, "activeRelease").mockResolvedValue(inUse);
  const { unmount } = renderWithClient(
    <ArchitectureRemapBanner mappedWith={["rel-2"]} canRemap busy={false} onRemap={vi.fn()} />,
  );
  await vi.waitFor(() => expect(active).toHaveBeenCalled());
  expect(screen.queryByRole("heading", { name: /older architecture catalogue/ })).not.toBeInTheDocument();
  unmount();

  renderWithClient(<ArchitectureRemapBanner mappedWith={[]} canRemap busy={false} onRemap={vi.fn()} />);
  expect(active).toHaveBeenCalledOnce();
});

it("lets people who cannot change the breakdown see why without the button", async () => {
  vi.spyOn(knowledgeApi, "activeRelease").mockResolvedValue(inUse);

  renderWithClient(<ArchitectureRemapBanner mappedWith={["rel-1"]} canRemap={false} busy={false} onRemap={vi.fn()} />);

  expect(await screen.findByRole("heading", { name: "Mapped with an older architecture catalogue" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Remap architecture" })).not.toBeInTheDocument();
});

it("stays quiet until a version in use is known", async () => {
  const active = vi.spyOn(knowledgeApi, "activeRelease").mockResolvedValue(null);

  renderWithClient(<ArchitectureRemapBanner mappedWith={["rel-1"]} canRemap busy={false} onRemap={vi.fn()} />);

  await vi.waitFor(() => expect(active).toHaveBeenCalled());
  expect(screen.queryByRole("heading", { name: /older architecture catalogue/ })).not.toBeInTheDocument();
});

it("names the version by its id when it has no name", async () => {
  vi.spyOn(knowledgeApi, "activeRelease").mockResolvedValue({ id: "rel-9", name: null });

  renderWithClient(<ArchitectureRemapBanner mappedWith={["rel-1"]} canRemap busy={false} onRemap={vi.fn()} />);

  expect(await screen.findByText(/“rel-9”, is in use/)).toBeVisible();
});
