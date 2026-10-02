import { jobFixture } from "../../test/jobFixture";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import {
  approvedFeatureFixture,
  splitProposalFixture,
  storyQualityFixture,
  storySetFixture,
} from "../../test/fixtures";
import { renderWithJobs } from "../../test/renderWithClient";
import { StoryList } from "./StoryList";

describe("StoryList", () => {
  beforeEach(() => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([]);
    vi.spyOn(api, "listStoryProposals").mockResolvedValue([]);
    vi.spyOn(api, "getFeatureStoryQualityAssessment").mockResolvedValue({
      feature_id: "feature-1",
      source_fingerprint: "current",
      generated_at: "2026-09-03T12:00:00Z",
      fresh: true,
      stories: [storyQualityFixture],
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("blocks Story generation until the Feature is approved and current", async () => {
    vi.spyOn(api, "getStories").mockResolvedValue({
      feature_id: "feature-1",
      stories: [],
      set_version: 1,
      generation_context_token: "story-set-context-1",
    });
    renderWithJobs(
      <StoryList requirementId="req-1" feature={{ ...approvedFeatureFixture, status: "generated" }} canManage />,
    );
    expect(
      await screen.findByText("Approve the Feature before generating its Stories."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate Stories" })).toBeDisabled();
  });

  it("generates Stories for an approved Feature", async () => {
    vi.spyOn(api, "getStories").mockResolvedValue({
      feature_id: "feature-1",
      stories: [],
      set_version: 1,
      generation_context_token: "story-set-context-1",
    });
    const generate = vi.spyOn(api, "startAiJob").mockResolvedValue(jobFixture);
    renderWithJobs(<StoryList requirementId="req-1" feature={approvedFeatureFixture} canManage />);
    const button = await screen.findByRole("button", { name: "Generate Stories" });
    expect(button).toBeEnabled();
    await userEvent.click(button);
    expect(generate).toHaveBeenCalledWith("req-1", {
      operation: "generate_stories",
      feature_id: "feature-1",
      context_token: "story-set-context-1",
    });
  });

  it("renders generated Stories with their voice lines", async () => {
    vi.spyOn(api, "getStories").mockResolvedValue(storySetFixture);
    renderWithJobs(<StoryList requirementId="req-1" feature={approvedFeatureFixture} canManage />);
    expect(await screen.findByText(/check my eligibility before ordering/)).toBeInTheDocument();
    expect(screen.getByText(/place an eligible order online/)).toBeInTheDocument();
    expect(screen.getByText("2 Stories")).toBeInTheDocument();
  });

  it("uses saved generation quality without scheduling evaluation", async () => {
    vi.spyOn(api, "getStories").mockResolvedValue(storySetFixture);
    const start = vi.spyOn(api, "startAiJob").mockResolvedValue(jobFixture);
    renderWithJobs(<StoryList requirementId="req-1" feature={approvedFeatureFixture} canManage />);
    expect(await screen.findByRole("region", { name: "INVEST quality review" })).toBeVisible();
    expect(start).not.toHaveBeenCalled();
  });

  it("offers explicit assessment for current content without saved quality", async () => {
    vi.spyOn(api, "getStories").mockResolvedValue(storySetFixture);
    vi.spyOn(api, "getFeatureStoryQualityAssessment").mockResolvedValue(null);
    const start = vi.spyOn(api, "startAiJob").mockResolvedValue(jobFixture);
    renderWithJobs(<StoryList requirementId="req-1" feature={approvedFeatureFixture} canManage />);
    const assess = await screen.findByRole("button", { name: "Check these Stories" });
    expect(start).not.toHaveBeenCalled();
    await userEvent.click(assess);
    expect(start).toHaveBeenCalledWith("req-1", expect.objectContaining({ operation: "evaluate_feature_quality" }), expect.any(String));
  });

  it("shows a pending split proposal and applies it only when confirmed", async () => {
    vi.spyOn(api, "getStories").mockResolvedValue(storySetFixture);
    vi.spyOn(api, "listStoryProposals").mockResolvedValue([splitProposalFixture]);
    const apply = vi.spyOn(api, "applyStoryProposal").mockResolvedValue(storySetFixture);
    renderWithJobs(<StoryList requirementId="req-1" feature={approvedFeatureFixture} canManage />);
    expect(await screen.findByText("Suggested by AI — read it before applying")).toBeInTheDocument();
    expect(screen.getByText(/enter my service address/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Apply proposal" }));
    await waitFor(() =>
      expect(apply).toHaveBeenCalledWith("req-1", "feature-1", "proposal-1", 1, 1),
    );
  });

  it("proposes a merge only once at least two Stories are selected", async () => {
    vi.spyOn(api, "getStories").mockResolvedValue(storySetFixture);
    const propose = vi.spyOn(api, "startAiJob").mockResolvedValue(jobFixture);
    renderWithJobs(<StoryList requirementId="req-1" feature={approvedFeatureFixture} canManage />);
    await screen.findByText(/check my eligibility before ordering/);
    const mergeButton = screen.getByRole("button", { name: /Propose merge/ });
    expect(mergeButton).toBeDisabled();
    const [first, second] = screen.getAllByRole("checkbox");
    await userEvent.click(first!);
    await userEvent.click(second!);
    expect(screen.getByRole("button", { name: /Propose merge \(2\)/ })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: /Propose merge \(2\)/ }));
    expect(propose).toHaveBeenCalledWith("req-1", {
      operation: "propose_story_change",
      feature_id: "feature-1",
      change_operation: "merge",
      source_story_ids: ["story-1", "story-2"],
      context_token: "story-set-context-1",
    });
  });

  it("regenerates an untouched set without force", async () => {
    vi.spyOn(api, "getStories").mockResolvedValue(storySetFixture);
    const regenerate = vi.spyOn(api, "startAiJob").mockResolvedValue(jobFixture);
    renderWithJobs(<StoryList requirementId="req-1" feature={approvedFeatureFixture} canManage />);

    await userEvent.click(await screen.findByRole("button", { name: "Regenerate all" }));
    expect(regenerate).toHaveBeenCalledWith("req-1", {
      operation: "regenerate_story_set",
      feature_id: "feature-1",
      force: false,
      context_token: "story-set-context-1",
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("requires confirmation and force before replacing an edited Story set", async () => {
    vi.spyOn(api, "getStories").mockResolvedValue({
      ...storySetFixture,
      stories: [{ ...storySetFixture.stories[0]!, status: "edited" }, storySetFixture.stories[1]!],
    });
    const regenerate = vi.spyOn(api, "startAiJob").mockResolvedValue(jobFixture);
    renderWithJobs(<StoryList requirementId="req-1" feature={approvedFeatureFixture} canManage />);

    await userEvent.click(await screen.findByRole("button", { name: "Regenerate all" }));
    expect(screen.getByRole("dialog", { name: "Replace all Stories?" })).toBeInTheDocument();
    expect(regenerate).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Replace all Stories" }));
    expect(regenerate).toHaveBeenCalledWith("req-1", {
      operation: "regenerate_story_set",
      feature_id: "feature-1",
      force: true,
      context_token: "story-set-context-1",
    });
  });

  it("manually splits a Story only after the replacement drafts are submitted", async () => {
    vi.spyOn(api, "getStories").mockResolvedValue(storySetFixture);
    const split = vi.spyOn(api, "splitStory").mockResolvedValue(storySetFixture);
    renderWithJobs(<StoryList requirementId="req-1" feature={approvedFeatureFixture} canManage />);

    const splitButtons = await screen.findAllByRole("button", { name: "Split by hand" });
    await userEvent.click(splitButtons[0]!);
    expect(screen.getByRole("dialog", { name: "Manually split Story" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Apply manual split" }));

    expect(split).toHaveBeenCalledWith(
      "req-1",
      "feature-1",
      "story-1",
      expect.arrayContaining([expect.objectContaining({ role: "SMB customer" })]),
      1,
    );
    expect(split.mock.calls[0]![3]).toHaveLength(2);
  });

  it("manually merges two selected sibling Stories", async () => {
    vi.spyOn(api, "getStories").mockResolvedValue(storySetFixture);
    const merge = vi.spyOn(api, "mergeStories").mockResolvedValue(storySetFixture);
    renderWithJobs(<StoryList requirementId="req-1" feature={approvedFeatureFixture} canManage />);

    await screen.findByText(/check my eligibility before ordering/);
    const [first, second] = screen.getAllByRole("checkbox");
    await userEvent.click(first!);
    await userEvent.click(second!);
    await userEvent.click(screen.getByRole("button", { name: "Manual merge (2)" }));
    expect(screen.getByRole("dialog", { name: "Manually merge Stories" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Apply manual merge" }));

    expect(merge).toHaveBeenCalledWith(
      "req-1",
      "feature-1",
      ["story-1", "story-2"],
      expect.objectContaining({ role: "SMB customer" }),
      1,
    );
  });

  it("keeps stale Stories visible while disabling all mutation controls", async () => {
    vi.spyOn(api, "getStories").mockResolvedValue({
      ...storySetFixture,
      stories: storySetFixture.stories.map((story) => ({
        ...story,
        stale: { reason: "feature_changed", since: "2026-01-01T13:00:00Z" },
      })),
    });
    renderWithJobs(
      <StoryList
        requirementId="req-1"
        feature={{
          ...approvedFeatureFixture,
          stale: { reason: "requirement_changed", since: "2026-01-01T13:00:00Z" },
        }}
        canManage
      />,
    );

    // One notice per stale Story, naming the reason and the remedy.
    expect(await screen.findAllByText(/parent Feature changed/)).toHaveLength(2);
    // Gated, not dead: it keeps its tab stop and says why.
    expect(screen.getByRole("button", { name: "Regenerate all" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getAllByRole("button", { name: "Edit" })[0]).toBeDisabled();
    // The gate reason is no longer `.control-reason`, which painted it
    // `--danger` and right-aligned it. A stale Feature is not an error — it is
    // a gate that explains itself — so it reads as muted meta beside the
    // controls it governs. The assertion is on the sentence, not the class.
    expect(screen.getByText(/source requirement changed/i)).toBeInTheDocument();
  });
});
