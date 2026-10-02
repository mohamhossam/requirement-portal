import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { knowledgeApi, type KnowledgeRelease } from "../../api/knowledge";
import { renderWithClient } from "../../test/renderWithClient";
import { ArchitectureRemapBanner } from "./ArchitectureRemapBanner";

const inUse = {
  id: "rel-2", revision: 3, status: "published", built_revision: 3, published_at: "2026-10-01T09:00:00Z",
  published_by: "amina", index_profile: "p", index_hash: "h", systems: [], relationships: [], documents: [],
  name: "October integration update", created_by: "amina",
} as KnowledgeRelease;

afterEach(() => vi.restoreAllMocks());

it("offers the team a confirmed remap when the breakdown uses an older version", async () => {
  vi.spyOn(knowledgeApi, "active").mockResolvedValue(inUse);
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

it("stays quiet when the mapping is current, unmapped, or the version in use is unreadable", async () => {
  const active = vi.spyOn(knowledgeApi, "active").mockResolvedValue(inUse);
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
  vi.spyOn(knowledgeApi, "active").mockResolvedValue(inUse);

  renderWithClient(<ArchitectureRemapBanner mappedWith={["rel-1"]} canRemap={false} busy={false} onRemap={vi.fn()} />);

  expect(await screen.findByRole("heading", { name: "Mapped with an older architecture catalogue" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Remap architecture" })).not.toBeInTheDocument();
});
