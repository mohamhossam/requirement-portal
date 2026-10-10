import { expect, type Download, type Locator, type Page, test } from "@playwright/test";

const apiUrl = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;
const structuredDocx = Buffer.from(
  "UEsDBBQAAAAIALh4J119j8M5TQAAAE0AAAATAAAAW0NvbnRlbnRfVHlwZXNdLnhtbLMJqSxILVaoyM3JK7ZVyigpKbDS1y9OzkjNTSzWyy9IzavIzUnLL8pNLCnWyy9K1y9ITM5OTE/VNzIwMNNPzs8rSc0r0S0BmaGkbwcAUEsDBBQAAAAIALh4J12FduB10wAAAMUBAAARAAAAd29yZC9kb2N1bWVudC54bWyVkcFqAjEQhl9l2QdwtIcewrqgC6WXgljqpfQQk3Q3MJksyWj07SXZVg+tlF7mg/D9+ZmkSUJ7dXCGuDo5pCjSsh6YRwEQ1WCcjDM/Gjo5/PTBSY4zH3pIPugxeGVitNQ7hIf5/BGctFS3TRJ7r8+ZYxmbUPDKZzRVEkeJy/rZSG2pX9TQNnB1yuD2ff3WLT5EtVJsj5Ktp+xwMcPkF3GPBVNKXQu/bnmyBvUvwXxS5J+RncSDuR/JmMw7ld0giQz+r3TdbV/+7MzI68L348Lt49oLUEsDBBQAAAAIALh4J10Ap/cAgwAAALIAAAAPAAAAd29yZC9zdHlsZXMueG1sRYxBCsMgEEWvInOATNJFFxKzbo8xJFYDjoojNbl9aCt09+H99+ampZ7Bijo4RNHNgK81a0RZvWWSIWUbDw6vVJiqDKk4bKlsuaTViuzRccDbON6RaY+wzD2omq5ntgYyFXKFsgfV0XMz8LC07dFNXyESf/5vCgb8D6gJcJmxG/8lywVQSwMEFAAAAAgAuHgnXXbgAUaeAAAABAEAABwAAAB3b3JkL19yZWxzL2RvY3VtZW50LnhtbC5yZWxzjc/NCsIwEATgVwm52y0igtL0UhUKepGi55Bu29D8kY0Q396LQgUPnof5hqmuaGTS3tGkA7FsjSPBp5TCHoDUhFZS4QO6bM3go5WJCh9HCFLNckRYl+UW4tLgdbU0WdsLHtt+x1n3DPiP7YdBKzx49bDo0o8JwJwwOmnO2s2cdTKOmARvmobdT7S6bYpsKH+Ci+9R8OO7wqGu4Ot0/QJQSwECFAAUAAAACAC4eCddfY/DOU0AAABNAAAAEwAAAAAAAAAAAAAAgAEAAAAAW0NvbnRlbnRfVHlwZXNdLnhtbFBLAQIUABQAAAAIALh4J12FduB10wAAAMUBAAARAAAAAAAAAAAAAACAAX4AAAB3b3JkL2RvY3VtZW50LnhtbFBLAQIUABQAAAAIALh4J10Ap/cAgwAAALIAAAAPAAAAAAAAAAAAAACAAYABAAB3b3JkL3N0eWxlcy54bWxQSwECFAAUAAAACAC4eCddduABRp4AAAAEAQAAHAAAAAAAAAAAAAAAgAEwAgAAd29yZC9fcmVscy9kb2N1bWVudC54bWwucmVsc1BLBQYAAAAABAAEAAcBAAAIAwAAAAA=",
  "base64",
);

async function downloadBytes(download: Download) {
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk));
  return Buffer.concat(chunks);
}

/**
 * Ownership and reviewer management are a panel, opened from the same button in
 * the same place on every stage (ux-plan.md §4). It used to be a `<details>` on
 * six routes and a drawer on the Backlog; it is the drawer everywhere now.
 *
 * Idempotent, because several of these flows reopen it after a persona switch.
 */
const openAccess = async (page: Page) => {
  const drawer = page.getByRole("dialog", { name: "People", exact: true });
  if (!(await drawer.isVisible())) {
    await page.getByRole("button", { name: "People", exact: true }).click();
    await expect(drawer).toBeVisible();
  }
  return drawer;
};

/** Modal, so anything in the header behind it has to wait for this. */
const closeAccess = async (page: Page) => {
  const drawer = page.getByRole("dialog", { name: "People", exact: true });
  if (await drawer.isVisible()) {
    await drawer.getByRole("button", { name: "Close", exact: true }).click();
    await expect(drawer).toHaveCount(0);
  }
};

/** The source is a panel too, and its "Edit source" lives inside it. */
const openSource = async (page: Page) => {
  const drawer = page.getByRole("dialog", { name: "Source document", exact: true });
  if (!(await drawer.isVisible())) {
    await page.getByRole("button", { name: "Source document", exact: true }).click();
    await expect(drawer).toBeVisible();
  }
  return drawer;
};

/**
 * Severity, blocker and assignee are triage, one click inside each question.
 *
 * Retried, not checked once: the row is an uncontrolled `<details>`, and a
 * refetch that lands after the click (a persona switch, a background knowledge
 * screen) remounts it closed. Converge on "open" instead of racing that.
 */
const openTriage = async (question: Locator) => {
  await expect(async () => {
    if (await question.getAttribute("open") === null) await question.locator("summary").first().click();
    await expect(question).toHaveAttribute("open", "", { timeout: 1_000 });
  }).toPass({ timeout: 15_000 });
};

test("login route presents responsive development access", async ({ page }, testInfo) => {
  await page.goto("/login?returnTo=%2Freports%3Fweeks%3D4");

  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await expect(page.getByText("Development mode")).toBeVisible();
  await expect(page.getByLabel("Test persona")).toHaveValue("fake-owner");
  await expect(page.getByRole("button", { name: "Continue to workspace" })).toBeEnabled();

  // The brand and the promise hold at every width; below `md` only the journey
  // rail folds away, so the sign-in panel arrives inside the first screen.
  await expect(page.getByText("Requirement AI", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Turn business needs into review-ready backlogs." })).toBeVisible();
  const journey = page.getByRole("list", { name: "Requirement breakdown journey" });
  if (testInfo.project.name === "chromium") {
    await expect(journey).toBeVisible();
  } else {
    await expect(journey).toBeHidden();
  }

  await page.getByRole("button", { name: "Continue to workspace" }).click();
  await expect(page).toHaveURL(/\/reports\?weeks=4$/);
});

/**
 * Model work runs only as a durable job (ADR-0105): start it, wait for the API's
 * worker to finish it, and fail the test with the job's own failure otherwise.
 */
async function runJob(page: Page, requirementId: string, operation: string, args: Record<string, unknown> = {}) {
  const jobs = `${apiUrl}/requirements/${requirementId}/ai-jobs`;
  const started = await page.request.post(jobs, {
    data: { operation, ...args },
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
  expect(started.ok(), await started.text()).toBeTruthy();
  const { id } = await started.json() as { id: string };
  let job = { status: "queued", failure: null as unknown };
  await expect(async () => {
    job = await (await page.request.get(`${jobs}/${id}`)).json() as typeof job;
    expect(["succeeded", "failed", "cancelled"]).toContain(job.status);
  }).toPass({ timeout: 30_000 });
  expect(job.status, JSON.stringify(job.failure)).toBe("succeeded");
}

async function postAnalysis(page: Page, requirementId: string, force = false) {
  const current = await page.request.get(`${apiUrl}/requirements/${requirementId}`);
  const requirement = await current.json() as { analysis_context_token: string };
  await runJob(page, requirementId, "analyse_requirement", {
    context_token: requirement.analysis_context_token,
    force,
  });
  return page.request.get(`${apiUrl}/requirements/${requirementId}/analysis`);
}

async function settleKnowledgeReview(page: Page, requirementId: string) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const response = await page.request.get(
      `${apiUrl}/requirements/${requirementId}/knowledge-review`,
    );
    const review = (await response.json()) as {
      ready?: boolean;
      status?: string;
      findings?: Array<{
        id: string;
        kind: "possible_duplicate" | "possible_contradiction";
        status: string;
        version: number;
      }>;
    };
    if (response.ok() && review.ready === true) return;
    if (response.ok() && review.status === "action_required") {
      for (const finding of review.findings ?? []) {
        const path = `${apiUrl}/requirements/${requirementId}/knowledge-findings/${finding.id}/decisions`;
        if (finding.kind === "possible_duplicate") {
          await page.request.post(path, {
            data: {
              decision: "distinct",
              expected_version: finding.version,
              text: "The smoke scenario is an independently governed test requirement.",
            },
          });
        } else if (finding.status === "open") {
          const proposed = await page.request.post(path, {
            data: {
              decision: "propose_resolution",
              expected_version: finding.version,
              text: "Each test Requirement keeps its independently stated scope.",
            },
          });
          const proposal = (await proposed.json()) as { version: number };
          await page.request.post(path, {
            data: { decision: "accept_resolution", expected_version: proposal.version },
          });
        } else {
          await page.request.post(path, {
            data: { decision: "accept_resolution", expected_version: finding.version },
          });
        }
      }
    }
    await page.waitForTimeout(200);
  }
  throw new Error(`Knowledge review for ${requirementId} did not become ready.`);
}

test("Knowledge entry lazily ensures one legacy screen without a rerender loop", async ({
  page,
}) => {
  const created = await page.request.post(`${apiUrl}/requirements`, {
    data: {
      title: "Legacy lazy-screen smoke",
      description: "Simulate a durable Requirement created before knowledge screening.",
    },
  });
  const requirement = (await created.json()) as { id: string };
  let ensureCalls = 0;
  await page.route(`**/requirements/${requirement.id}/knowledge-review`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "required",
        current: false,
        ready: false,
        input_fingerprint: "legacy-screen-fingerprint",
        screen_id: null,
        provenance: null,
        findings: [],
      }),
    }),
  );
  await page.route(`**/requirements/${requirement.id}/ai-jobs*`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route(`**/requirements/${requirement.id}/knowledge-screen/ensure`, (route) => {
    ensureCalls += 1;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ outcome: "scheduled", job_id: "lazy-screen-job" }),
    });
  });

  await page.goto(`/requirements/${requirement.id}/knowledge`);

  await expect(page.getByRole("heading", { name: "Screening in progress" })).toBeVisible();
  await page.waitForTimeout(500);
  expect(ensureCalls).toBe(1);
});

async function resolveAndConfirmAnalysis(page: Page) {
  await expect(page.getByText("Drafted by the analysis", { exact: true })).toBeVisible();
  const questions = page.locator("details").filter({ has: page.getByLabel("Your answer", { exact: true }) });
  await expect(questions).toHaveCount(4);
  for (const question of await questions.all()) await openTriage(question);
  await expect(questions.first().getByText("Suggested answers, from the evidence")).toBeVisible();
  const answers = [
    "Confirmed by the Requirement Owner.",
    "Product Operations owns the decision.",
    "Use the assisted channel interpretation.",
    "The dependency is available.",
  ];
  const answerInputs = page.getByLabel("Your answer");
  await expect(answerInputs).toHaveCount(answers.length);
  for (const [index, answer] of answers.entries()) {
    await answerInputs.nth(index).fill(answer);
  }
  await page.getByRole("button", { name: "Send 4 answers and re-analyse" }).click();
  await expect(page.getByLabel("Your answer")).toHaveCount(0);
  await expect(page.getByText("Every earlier round (2)")).toBeVisible();
  const proposal = page.getByRole("button", { name: "Accept as written", exact: true });
  if (await proposal.count()) {
    await proposal.first().click();
    await expect(page.getByRole("button", { name: "Accept as written", exact: true })).toHaveCount(0);
  }
  await expect(page.getByLabel("Your answer")).toHaveCount(0);
  const requirementId = page.url().match(/\/requirements\/([^/]+)/)?.[1];
  if (!requirementId) throw new Error("Requirement ID is missing from the workspace URL.");
  await settleKnowledgeReview(page, requirementId);
  await page.goto(`/requirements/${requirementId}/knowledge`);
  await expect(page.getByRole("heading", { name: "Knowledge review clear" })).toBeVisible();
  await page.goto(`/requirements/${requirementId}/clarify`);
  const confirm = page.getByRole("button", { name: "Confirm this analysis" });
  await expect(confirm).toBeEnabled({ timeout: 20_000 });
  await confirm.click();
  await expect(page).toHaveURL(/\/breakdown\/epic$/);
}

async function createGovernableBacklog(page: Page) {
  const created = await page.request.post(`${apiUrl}/requirements`, {
    data: { title: "Approval workflow smoke", description: "Govern a complete fake backlog." },
  });
  const requirement = await created.json() as { id: string };
  const generatedAnalysisResponse = await postAnalysis(page, requirement.id);
  const generatedAnalysis = await generatedAnalysisResponse.json() as { version: number };
  await runJob(page, requirement.id, "clarify_requirement_analysis", {
    answers: [
      { kind: "assumption", subject: "This is an assumption.", answer: "Confirmed." },
      { kind: "open_question", subject: "Is this a question?", answer: "Yes." },
      { kind: "ambiguity", subject: "This is ambiguous.", answer: "Use the first interpretation." },
      { kind: "potential_dependency", subject: "This is a dependency.", answer: "Available." },
    ],
    expected_analysis_version: generatedAnalysis.version,
  });
  const clarified = await page.request.get(`${apiUrl}/requirements/${requirement.id}/analysis`);
  const analysis = await clarified.json() as {
    business_intent: { proposals: Array<{ id: string; status: string; version: number }> };
  };
  for (const proposal of analysis.business_intent.proposals.filter((item) => item.status === "pending")) {
    await page.request.patch(
      `${apiUrl}/requirements/${requirement.id}/analysis/proposals/${proposal.id}`,
      { data: { decision: "accepted", expected_version: proposal.version } },
    );
  }
  await settleKnowledgeReview(page, requirement.id);
  const currentAnalysisResponse = await page.request.get(
    `${apiUrl}/requirements/${requirement.id}/analysis`,
  );
  const currentAnalysis = await currentAnalysisResponse.json() as {
    version: number;
    epic_context_token: string;
  };
  await page.request.post(`${apiUrl}/requirements/${requirement.id}/analysis/confirmation`, {
    data: { expected_version: currentAnalysis.version },
  });
  const confirmedAnalysisResponse = await page.request.get(
    `${apiUrl}/requirements/${requirement.id}/analysis`,
  );
  const confirmedAnalysis = await confirmedAnalysisResponse.json() as {
    epic_context_token: string;
  };
  await runJob(page, requirement.id, "generate_epic", {
    context_token: confirmedAnalysis.epic_context_token,
  });
  const epicResponse = await page.request.get(`${apiUrl}/requirements/${requirement.id}/epic`);
  const epic = await epicResponse.json() as {
    version: number;
    content_fingerprint: string;
  };
  const approvedEpicResponse = await page.request.post(
    `${apiUrl}/requirements/${requirement.id}/epic/approval`,
    { data: {
      expected_version: epic.version,
      expected_content_fingerprint: epic.content_fingerprint,
    } },
  );
  expect(approvedEpicResponse.ok()).toBeTruthy();
  const currentEpicResponse = await page.request.get(
    `${apiUrl}/requirements/${requirement.id}/epic`,
  );
  const currentEpic = await currentEpicResponse.json() as { feature_context_token: string };
  await runJob(page, requirement.id, "generate_features", {
    context_token: currentEpic.feature_context_token,
  });
  const featureResponse = await page.request.get(`${apiUrl}/requirements/${requirement.id}/features`);
  expect(featureResponse.ok()).toBeTruthy();
  const features = await featureResponse.json() as {
    features: Array<{
      id: string;
      version: number;
      content_fingerprint: string;
    }>;
  };
  const stories: Array<{ id: string; featureId: string }> = [];
  for (const feature of features.features) {
    const approvedFeatureResponse = await page.request.post(
      `${apiUrl}/requirements/${requirement.id}/features/${feature.id}/approval`,
      { data: {
        expected_version: feature.version,
        expected_content_fingerprint: feature.content_fingerprint,
      } },
    );
    expect(approvedFeatureResponse.ok()).toBeTruthy();
    const currentFeaturesResponse = await page.request.get(
      `${apiUrl}/requirements/${requirement.id}/features`,
    );
    const currentFeatures = await currentFeaturesResponse.json() as {
      features: Array<{ id: string; story_context_token: string }>;
    };
    const currentFeature = currentFeatures.features.find((item) => item.id === feature.id);
    expect(currentFeature).toBeTruthy();
    await runJob(page, requirement.id, "generate_stories", {
      context_token: currentFeature!.story_context_token,
      feature_id: feature.id,
    });
    const storyResponse = await page.request.get(
      `${apiUrl}/requirements/${requirement.id}/features/${feature.id}/stories`,
    );
    expect(storyResponse.ok()).toBeTruthy();
    const body = await storyResponse.json() as {
      stories: Array<{ id: string; version: number; content_fingerprint: string }>;
    };
    for (const story of body.stories) {
      await page.request.post(
        `${apiUrl}/requirements/${requirement.id}/features/${feature.id}/stories/${story.id}/approval`,
        { data: {
          expected_version: story.version,
          expected_content_fingerprint: story.content_fingerprint,
        } },
      );
      stories.push({ id: story.id, featureId: feature.id });
    }
  }
  await runJob(page, requirement.id, "generate_breakdown_review");
  const accessResponse = await page.request.get(
    `${apiUrl}/requirements/${requirement.id}/assignments`,
  );
  const access = await accessResponse.json() as { version: number };
  await page.request.put(`${apiUrl}/requirements/${requirement.id}/reviewers/fake-reviewer`, {
    data: { expected_version: access.version },
  });
  return { requirementId: requirement.id, firstStory: stories[0]! };
}

test("submitted Story rejection is revised, resubmitted, and finally approved", async ({ page }) => {
  const { requirementId, firstStory } = await createGovernableBacklog(page);
  await page.goto(`/requirements/${requirementId}/review`);
  await expect(page.getByRole("heading", { name: "Sign off this backlog" })).toBeVisible();

  await page.getByRole("button", { name: "Submit for review" }).click();
  await page.getByRole("dialog", { name: "Submit this backlog?" }).getByRole("button", { name: "Submit backlog" }).click();
  // The lifecycle names the current stage; the strip above repeats it for scanning.
  const effectiveStatus = page.getByRole("list", { name: "Approval lifecycle" }).locator("[aria-current=step]");
  await expect(effectiveStatus).toContainText("Under review");

  await page.getByLabel("Development persona").selectOption("fake-reviewer");
  await page.getByRole("list", { name: "Story decisions" }).getByRole("listitem").first().getByRole("button", { name: "Reject" }).click();
  const reject = page.getByRole("dialog", { name: "Reject this Story?" });
  await reject.getByLabel("Reason").fill("Add the failure path before approval.");
  await reject.getByRole("button", { name: "Reject Story" }).click();
  await expect(effectiveStatus).toContainText("Needs revision");

  await page.getByLabel("Development persona").selectOption("fake-owner");
  await page.goto(`/requirements/${requirementId}/breakdown/features/${firstStory.featureId}/stories/${firstStory.id}`);
  const story = page.locator(`#story-${firstStory.id}`);
  await story.getByRole("button", { name: "Edit" }).click();
  const storyEditor = page.locator("form.story-editor");
  await storyEditor.getByLabel("So that").fill("I receive service and understand the failure path");
  await storyEditor.getByRole("button", { name: "Save Story" }).click();

  await page.goto(`/requirements/${requirementId}/review`);
  await page.getByRole("button", { name: "Refresh review" }).click();
  await expect(page.getByText("This review is stale.")).not.toBeVisible({ timeout: 20_000 });
  const target = page.getByRole("list", { name: "Story decisions" }).getByRole("listitem").filter({ hasText: "understand the failure path" });
  await target.getByRole("button", { name: "Approve" }).click();
  await expect(target).toContainText("Approved by Amina Owner");

  await page.getByRole("button", { name: "Submit for review" }).click();
  await page.getByRole("dialog", { name: "Submit this backlog?" }).getByRole("button", { name: "Submit backlog" }).click();
  await page.getByRole("button", { name: "Final approval" }).click();
  const finalApproval = page.getByRole("dialog", { name: "Grant final approval?" });
  await finalApproval.getByLabel("Rationale (optional)").fill("Complete and current.");
  await finalApproval.getByRole("button", { name: "Grant final approval" }).click();
  await expect(effectiveStatus).toContainText("Approved");

  await page.goto(`/requirements/${requirementId}/revisions`);
  await expect(page.getByRole("heading", { name: /Approved backlog/ })).toBeVisible();
  await expect(page.getByText(/^Approved by Amina Owner on /)).toBeVisible();
  const download = page.getByRole("button", { name: /^Download version \d+$/ });
  await expect(page.getByRole("radio", { name: /^JSON/ })).toBeChecked();
  const jsonStarted = page.waitForEvent("download");
  await download.click();
  const jsonDownload = await jsonStarted;
  expect(jsonDownload.suggestedFilename()).toMatch(/breakdown-v\d+\.json$/);
  const json = JSON.parse((await downloadBytes(jsonDownload)).toString("utf8")) as {
    schema_version: string;
    epic: { features: Array<{ stories: unknown[] }> };
  };
  expect(json.schema_version).toBe("1.5");
  expect(json.epic.features[0]!.stories.length).toBeGreaterThan(0);

  await page.getByRole("radio", { name: /^Excel workbook/ }).check();
  const xlsxStarted = page.waitForEvent("download");
  await download.click();
  const xlsxDownload = await xlsxStarted;
  expect(xlsxDownload.suggestedFilename()).toMatch(/breakdown-v\d+\.xlsx$/);
  expect((await downloadBytes(xlsxDownload)).subarray(0, 2).toString()).toBe("PK");

  await page.goto(`/requirements/${requirementId}/review`);
  await expect(page.getByRole("list", { name: "Approval lifecycle" }).locator("[aria-current=step]")).toContainText("Approved");
  await expect(page.getByText("Complete and current.")).toBeVisible();
});

test("owner assigns a reviewer who drafts and resolves before owner confirmation", async ({ page }) => {
  const created = await page.request.post(`${apiUrl}/requirements`, {
    data: { title: "Collaborative clarification smoke", description: "Audit team answers." },
  });
  const requirement = await created.json() as { id: string };
  expect((await postAnalysis(page, requirement.id)).ok()).toBeTruthy();
  await page.goto(`/requirements/${requirement.id}/clarify`);

  const access = await openAccess(page);
  await access.getByLabel("Known actor").selectOption("fake-reviewer");
  await access.getByRole("button", { name: "Add reviewer" }).click();
  await closeAccess(page);
  await openTriage(page.locator("details").filter({ has: page.locator("summary", { hasText: "Is this a question?" }) }).first());
  await page.getByLabel("Who answers: Is this a question?").selectOption("fake-reviewer");
  await expect(page.getByLabel("Who answers: Is this a question?")).toHaveValue("fake-reviewer");

  // A persona switch hides the page, then remounts it keyed on the new actor
  // (AuthGate), so the row the owner opened is replaced by a closed one. The
  // select only shows the reviewer once that remount has happened; act after it.
  await page.getByLabel("Development persona").selectOption("fake-reviewer");
  await expect(page.getByLabel("Development persona")).toHaveValue("fake-reviewer");
  const question = page.locator("details").filter({ has: page.locator("summary", { hasText: "Is this a question?" }) }).first();
  await openTriage(question);
  await question.getByLabel("Your answer").fill("Customer Operations owns the decision.");
  await question.getByRole("button", { name: "Save as a draft" }).click();
  await expect(question.getByText(/Draft saved by Ravi Reviewer/)).toBeVisible();
  await page.getByRole("button", { name: "Send 1 answer and re-analyse" }).click();
  await expect(page.getByText("Every earlier round (2)")).toBeVisible();
  // Four labelled counts since Phase 2, not a sentence.
  await expect(page.getByRole("status", { name: "Since the last round" })).toContainText(/Kept\s*3/);

  await page.getByLabel("Development persona").selectOption("fake-owner");
  await expect(page.getByLabel("Development persona")).toHaveValue("fake-owner");
  await expect(page.getByRole("button", { name: "Accept as written", exact: true })).toBeEnabled();
  const remainingQuestions = page.locator("details").filter({ has: page.getByLabel("Your answer", { exact: true }) });
  const remainingCount = 3;
  await expect(remainingQuestions).toHaveCount(remainingCount);
  for (let index = 0; index < remainingCount; index += 1) {
    const question = remainingQuestions.nth(index);
    await openTriage(question);
    await question.getByLabel("Your answer", { exact: true }).fill(`Owner resolution ${index + 1}.`);
  }
  await page.getByRole("button", {
    name: `Send ${remainingCount} answers and re-analyse`,
  }).click();
  await expect(page.getByLabel("Your answer")).toHaveCount(0);
  await page.getByRole("button", { name: "Accept as written", exact: true }).click();
  await expect(page.getByRole("button", { name: "Accept as written", exact: true })).toHaveCount(0);
  await settleKnowledgeReview(page, requirement.id);
  await page.reload();
  const confirm = page.getByRole("button", { name: "Confirm this analysis" });
  await expect(confirm).toBeEnabled({ timeout: 20_000 });
  await page.waitForTimeout(500);
  await confirm.click();
  await expect(page).toHaveURL(/\/breakdown\/epic$/);
});

test("two Requirement owners approve one shared contradiction resolution", async ({ page }, testInfo) => {
  const prefix = testInfo.project.name.replaceAll("-", "");
  const scope = Array.from({ length: 12 }, (_, index) => `${prefix}scope${index}`).join(" ");
  const canonicalResponse = await page.request.post(`${apiUrl}/requirements`, {
    data: {
      title: `${prefix} activation policy`,
      description: `${scope} policy permits customers to activate service.`,
    },
    headers: { "X-Fake-Actor-Id": "fake-owner" },
  });
  const canonical = (await canonicalResponse.json()) as { id: string };
  const candidateResponse = await page.request.post(`${apiUrl}/requirements`, {
    data: {
      title: `${prefix} activation policy exception`,
      description: `${scope} policy does not permit customers to activate service.`,
    },
    headers: { "X-Fake-Actor-Id": "fake-reviewer" },
  });
  const candidate = (await candidateResponse.json()) as { id: string };

  await expect.poll(async () => {
    const response = await page.request.get(
      `${apiUrl}/requirements/${candidate.id}/knowledge-review`,
    );
    const review = (await response.json()) as {
      findings?: Array<{ kind: string; status: string; related_requirement_id: string; subject_requirement_id: string }>;
    };
    return review.findings?.some(
      (finding) => finding.kind === "possible_contradiction" && finding.status === "open" && [finding.related_requirement_id, finding.subject_requirement_id].includes(canonical.id),
    ) ?? false;
  }, { timeout: 20_000 }).toBe(true);

  await page.goto(`/requirements/${canonical.id}/knowledge`);
  const contradiction = page.getByRole("article").filter({
    hasText: "Possible contradiction",
    has: page.locator(`a[href="/requirements/${candidate.id}/knowledge"]`),
  });
  await contradiction.getByLabel("How the two requirements fit together").fill(
    "The exception governs only accounts without an active service agreement.",
  );
  await contradiction.getByRole("button", { name: "Propose shared resolution" }).click();
  await contradiction.getByRole("button", { name: "Accept shared resolution" }).click();
  await expect(contradiction).toContainText("Accepted by 1 owner.");

  await page.getByLabel("Development persona").selectOption("fake-reviewer");
  await page.goto(`/requirements/${candidate.id}/knowledge`);
  const linkedContradiction = page.getByRole("article").filter({
    hasText: "Possible contradiction",
    has: page.locator(`a[href="/requirements/${canonical.id}/knowledge"]`),
  });
  await linkedContradiction.getByRole("button", { name: "Accept shared resolution" }).click();
  await expect(linkedContradiction).toHaveCount(0);
});

test("Product Owner completes the desktop journey and sees worklist staleness", async ({ page }) => {
  const standaloneChecks: string[] = [];
  const prematureBacklogReads: string[] = [];
  page.on("request", (request) => {
    if (/\/(capture|clarify|knowledge|confirm)$/.test(page.url()) && request.method() === "GET" && /\/requirements\/[^/]+\/(epic|features|revisions)(?:[/?]|$)/.test(request.url())) {
      prematureBacklogReads.push(request.url());
    }
    if (request.method() === "POST" && request.url().endsWith("/ai-jobs")) {
      const operation = (request.postDataJSON() as { operation?: string }).operation;
      if (operation === "evaluate_feature_quality" || operation === "generate_breakdown_review") standaloneChecks.push(operation);
    }
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Requirements", exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/wireframe-dashboard.png", fullPage: true });

  await page.getByRole("link", { name: "New requirement", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "New requirement" })).toBeVisible();
  await page.screenshot({ path: "test-results/wireframe-intake.png", fullPage: true });
  await page.getByLabel(/Requirement title/).fill("High-speed business bundles");
  await page.getByLabel(/Business need/).fill(
    "Make XGPON business bundles available for eligible SMB customers in assisted channels.",
  );
  await page.getByText("Add detail if you know it (optional)").click();
  await page.getByLabel("Systems involved").fill("BCRM\nCPP");
  await page.getByRole("button", { name: "Save and analyse", exact: true }).click();
  await expect(page).toHaveURL(/\/requirements\//);

  await expect(page.getByText("Drafted by the analysis", { exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/wireframe-clarification.png", fullPage: true });
  expect(prematureBacklogReads).toEqual([]);
  await resolveAndConfirmAnalysis(page);
  expect(prematureBacklogReads).toEqual([]);
  await page.getByRole("button", { name: "Generate Epic" }).click();
  const epicCard = page.locator("article.epic-card");
  await expect(epicCard).toContainText("Generated");
  await epicCard.getByRole("button", { name: "Approve" }).click();

  await page.getByRole("button", { name: "Decompose into Features" }).click();
  const featureCards = page.locator("article.feature-card");
  await expect(featureCards).toHaveCount(2, { timeout: 20_000 });
  await page.locator(".backlog-child-list li a").first().click();
  const firstFeature = featureCards.first();
  await firstFeature.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Feature name").fill("Human-reviewed ordering");
  await page.getByRole("button", { name: "Save Feature" }).click();
  const reviewedFeature = page.locator("article.feature-card", {
    hasText: "Human-reviewed ordering",
  });
  await expect(reviewedFeature).toBeVisible();
  await reviewedFeature.getByRole("button", { name: "Approve" }).click();
  await expect(reviewedFeature.getByText("Approved", { exact: true })).toBeVisible({
    timeout: 20_000,
  });

  await page.getByRole("button", { name: "Generate Stories" }).click();
  const storyLink = page.locator(".compact-story-list a").first();
  await expect(storyLink).toBeVisible({ timeout: 20_000 });
  await storyLink.click();
  const storyCard = page.locator("article.story-card:visible").first();
  await expect(storyCard).toContainText("As a", { timeout: 20_000 });
  await expect(storyCard).toContainText("Given");
  await expect(storyCard).toContainText("When");
  await expect(storyCard).toContainText("Then");
  await expect(
    page.getByRole("region", { name: "INVEST quality review" }).first(),
  ).toContainText("Passes all checks");
  // Step 6 of the stage rail, not a button in the Backlog page header
  // (ux-plan.md §3.2, §4).
  await page.getByRole("navigation", { name: "Requirement workflow" })
    .getByRole("link", { name: /^Review & approve/ }).click();
  await expect(page.getByRole("heading", { name: "Concerns to resolve" })).toBeVisible();
  expect(standaloneChecks).toEqual([]);
  await page.goBack();


  await storyCard.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("So that").fill("I avoid starting an order I cannot finish");
  await page.getByRole("button", { name: "Save Story" }).click();
  const editedStory = page.locator("article.story-card:visible", {
    hasText: "I avoid starting an order I cannot finish",
  });
  await expect(editedStory).toBeVisible();
  await editedStory.getByText("More actions", { exact: true }).click();
  await editedStory.getByRole("button", { name: "Regenerate Story" }).click();
  const storyDialog = page.getByRole("dialog", { name: "Replace this Story?" });
  await expect(storyDialog).toBeVisible();
  await storyDialog.getByRole("button", { name: "Cancel" }).click();

  await editedStory.getByRole("button", { name: "Suggest a split" }).click();
  const proposal = page.getByRole("region", { name: "Pending split proposal" });
  await expect(proposal.getByText("Suggested by AI — read it before applying")).toBeVisible();
  await page.getByRole("button", { name: "Apply proposal" }).click();
  await page.locator(".backlog-breadcrumbs a").last().click();
  await expect(page.locator(".compact-story-list li")).toHaveCount(3);
  // Map / Refresh architecture lives inside the card's System impact now,
  // beside the result it produces, not in a disclosure of its own below it.
  await reviewedFeature.getByText("System impact", { exact: true }).click();

  // A manual Feature edit above cleared its mapping; explicitly refresh that edited source.
  await reviewedFeature.getByRole("button", { name: "Map architecture" }).click();
  await expect(reviewedFeature.getByRole("button", { name: "Refresh architecture" })).toBeVisible();
  await expect(reviewedFeature.getByText("Crosses systems").first()).toBeVisible();
  await expect(reviewedFeature.getByText("Not in the catalogue").first()).toBeVisible();
  await expect(reviewedFeature.getByRole("term").filter({ hasText: /^Squads$/ }).first()).toBeVisible();
  await expect(reviewedFeature.getByRole("definition").filter({ hasText: /^not assigned$/ }).first()).toBeVisible();

  // Step 6 of the stage rail, not a button in the Backlog page header
  // (ux-plan.md §3.2, §4).
  await page.getByRole("navigation", { name: "Requirement workflow" })
    .getByRole("link", { name: /^Review & approve/ }).click();
  await expect(page).toHaveURL(/\/review$/);
  await page.getByRole("button", { name: "Refresh review" }).click();
  await expect(page.getByRole("heading", { name: "Concerns to resolve" })).toBeVisible();
  const decisionFlag = page.getByRole("region", { name: "Concerns to resolve" }).getByRole("listitem").filter({ hasText: "Cross-system Feature" }).filter({ hasText: "Human-reviewed ordering" });
  await expect(decisionFlag.getByText("Cross-system Feature")).toBeVisible();
  await decisionFlag.getByRole("button", { name: "Resolve with decision" }).click();
  await decisionFlag.getByLabel("Decision").fill("Coordinate as one delivery Feature");
  await decisionFlag.getByLabel("Rationale").fill("The same team owns both system changes.");
  await decisionFlag.getByRole("button", { name: "Confirm resolution" }).click();
  await expect(decisionFlag.getByText("Resolved", { exact: true })).toBeVisible();
  await expect(page.getByText("Coordinate as one delivery Feature")).toBeVisible();
  await page.screenshot({ path: "test-results/breakdown-review.png", fullPage: true });

  const sourcePanel = await openSource(page);
  await sourcePanel.getByRole("button", { name: "Edit source" }).click();
  await sourcePanel.getByLabel(/Requirement title/).fill("Updated high-speed business bundles");
  await sourcePanel.getByLabel(/Business need/).fill(
    "Updated requirement for eligible XGPON SMB customers in BCRM and CPP.",
  );
  await sourcePanel.getByRole("button", { name: "Save requirement" }).click();
  const impactDialog = page.getByRole("dialog", { name: "Save source changes?" });
  await expect(impactDialog).toBeVisible();
  await impactDialog.getByRole("button", { name: "Acknowledge and save" }).click();
  // The panel stays open and returns to reading: saving the source is not a
  // reason to take the source away from the person who just edited it.
  await expect(sourcePanel.getByRole("button", { name: "Edit source" })).toBeVisible();
  await sourcePanel.getByRole("button", { name: "Close", exact: true }).click();
  await expect(sourcePanel).toHaveCount(0);

  await expect(page.getByText("This review is stale.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Record a decision" })).toBeDisabled();
  await page.goto(page.url().replace(/\/review$/, "/breakdown"));
  await expect(page.locator(".backlog-detail .epic-card .stale-notice")).toBeVisible();
  await expect(epicCard.getByText("Out of date").first()).toBeVisible();
  await page.locator(".backlog-child-list li a").first().click();
  await expect(page.locator(".compact-story-list li")).toHaveCount(3);
  await page.locator(".compact-story-list a").first().click();
  await expect(page.locator(".story-card:visible .stale-notice")).toBeVisible();
  await expect(page.getByText("Confirm the analysis to change the backlog")).toBeVisible();

  await page.locator("a.brand-lockup").click();
  await expect(page).toHaveURL(/\/$/);
  const updatedRow = page.locator("[data-worklist-row]", {
    hasText: "Updated high-speed business bundles",
  }).first();
  await expect(updatedRow).toBeVisible();
  await expect(updatedRow).toContainText("Stale");
  await updatedRow.click();
  // The h1 is the requirement, not the stage (ux-plan.md §3.4): a person with
  // four of these open is looking for which requirement, and the stage is named
  // by the rail and by the line under the title.
  await expect(
    page.getByRole("heading", { level: 1, name: "Updated high-speed business bundles" }),
  ).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Requirement workflow" })
    .locator("li.viewing")).toContainText("Review & approve");
  expect(prematureBacklogReads).toEqual([]);
});

test("Author uploads, selects, and reviews immutable source documents", async ({ page }, testInfo) => {
  const filename = `${testInfo.project.name}-structured.docx`;
  const created = await page.request.post(`${apiUrl}/requirements`, {
    data: { title: "Document-backed requirement", description: "Use supplied policy evidence." },
  });
  expect(created.ok()).toBeTruthy();
  const requirement = await created.json() as { id: string };
  await page.goto(`/requirements/${requirement.id}/capture`);

  await expect(page.getByLabel("Attach files", { exact: true })).toBeEnabled();
  await page.getByLabel("Attach files", { exact: true }).setInputFiles({
    name: filename,
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: structuredDocx,
  });
  await expect(page.getByRole("status").filter({ hasText: "Processing continues in the background" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Include in analysis" })).toBeChecked();

  await page.goto("/documents");
  await expect(page.getByRole("heading", { name: "Documents", exact: true })).toBeVisible();
  await page.screenshot({
    path: `test-results/source-document-catalogue-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await page.getByRole("link", { name: new RegExp(filename) }).click();
  await expect(page.getByRole("heading", { name: "What analysis reads" })).toBeVisible();
  // The Word table's rows are drawn as the table they came from.
  const table = page.getByRole("table", { name: /^Table 1/ });
  await expect(table.getByRole("row").filter({ hasText: "Channel" }).getByRole("cell", { name: "BCRM", exact: true })).toBeVisible();
  await expect(page.getByText(/CCC WFs-V4.xlsx.*upload it separately/)).toBeVisible();
  const analyzed = await postAnalysis(page, requirement.id);
  expect(analyzed.ok()).toBeTruthy();
  await page.goto(`/requirements/${requirement.id}/clarify`);
  await page.getByRole("button", { name: /Where this came from:/ }).first().click();
  const source = page.getByRole("dialog", { name: "Where this came from", exact: true }).getByRole("link", { name: /Open this passage/ }).first();
  const opened = page.waitForEvent("popup");
  await source.click();
  const sourcePage = await opened;
  await expect(sourcePage).toHaveURL(/\/documents\/.+#block-/);
  await expect(page).toHaveURL(new RegExp(`/requirements/${requirement.id}/clarify$`));
  await sourcePage.getByLabel("Upload new version").setInputFiles({
    name: filename,
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: structuredDocx,
  });
  await expect(sourcePage.getByText("Version 2", { exact: true })).toBeVisible();
  await expect(sourcePage.getByRole("checkbox", { name: "Include in analysis" })).not.toBeChecked();
});

test("owner and reviewer identities enforce assignments and private drafts", async ({ page }) => {
  const created = await page.request.post(`${apiUrl}/requirements`, {
    data: { title: "Identity assignment smoke", description: "Verify owner and reviewer access." },
  });
  expect(created.ok()).toBeTruthy();
  const requirement = await created.json() as { id: string };
  expect((await postAnalysis(page, requirement.id)).ok()).toBeTruthy();
  const accessResponse = await page.request.get(
    `${apiUrl}/requirements/${requirement.id}/assignments`,
  );
  const access = await accessResponse.json() as { version: number };
  expect((await page.request.put(
    `${apiUrl}/requirements/${requirement.id}/reviewers/fake-reviewer`,
    { data: { expected_version: access.version } },
  )).ok()).toBeTruthy();

  const draft = await page.request.post(`${apiUrl}/requirements/drafts`, {
    data: {
      title: "Owner private draft",
      description: "",
      desired_outcome: "",
      customer_context: "",
      channels: [],
      systems: [],
      business_rules: [],
      constraints: [],
    },
  });
  expect(draft.ok()).toBeTruthy();

  await page.goto("/");
  await page.getByRole("checkbox", { name: "Assigned to me" }).check();
  await expect(page.getByText("Identity assignment smoke").first()).toBeVisible();

  await page.getByLabel("Development persona").selectOption("fake-reviewer");
  await expect(page.getByLabel("Development persona")).toHaveValue("fake-reviewer");
  await expect(page.getByText("Identity assignment smoke").first()).toBeVisible();
  await expect(page.getByText("Owner private draft")).not.toBeVisible();

  const reviewerHeaders = { "X-Fake-Actor-Id": "fake-reviewer" };
  const reviewerAnalysisResponse = await page.request.get(
    `${apiUrl}/requirements/${requirement.id}/analysis`,
    { headers: reviewerHeaders },
  );
  const reviewerAnalysis = await reviewerAnalysisResponse.json() as { version: number };
  expect((await page.request.post(
    `${apiUrl}/requirements/${requirement.id}/analysis/confirmation`,
    {
      headers: reviewerHeaders,
      data: { expected_version: reviewerAnalysis.version },
    },
  )).status()).toBe(403);
  expect((await page.request.put(
    `${apiUrl}/requirements/${requirement.id}/reviewers/fake-observer`,
    {
      headers: reviewerHeaders,
      data: { expected_version: access.version + 1 },
    },
  )).status()).toBe(403);

  await page.goto(`/requirements/${requirement.id}/confirm`);
  let people = await openAccess(page);
  await expect(people.getByText(/Only Amina Owner/).first()).toBeVisible();
  await expect(people.getByRole("button", { name: "Add reviewer" })).not.toBeVisible();
  await closeAccess(page);

  await page.getByLabel("Development persona").selectOption("fake-owner");
  people = await openAccess(page);
  await people.getByLabel("Known actor").selectOption("fake-reviewer");
  await people.getByRole("button", { name: "Transfer ownership" }).click();
  await page.getByRole("dialog", { name: "Transfer ownership?" }).getByRole("button", { name: "Transfer ownership" }).click();
  await expect(people.getByRole("region", { name: "Owner" })).toContainText("Ravi Reviewer");
  await closeAccess(page);

  await page.getByLabel("Development persona").selectOption("fake-reviewer");
  people = await openAccess(page);
  await expect(people.getByRole("button", { name: "Add reviewer" })).toBeVisible();
  await closeAccess(page);
  const mine = await page.request.get(`${apiUrl}/requirements?assigned_to_me=true`, {
    headers: reviewerHeaders,
  });
  expect((await mine.json() as { requirements: Array<{ id: string }> }).requirements)
    .toContainEqual(expect.objectContaining({ id: requirement.id }));
  const reviewerDrafts = await page.request.get(`${apiUrl}/requirements/drafts`, {
    headers: reviewerHeaders,
  });
  expect((await reviewerDrafts.json() as { drafts: unknown[] }).drafts).toEqual([]);
});

test("reviewer saves a worklist view and drills through activity and reporting", async ({ page }, testInfo) => {
  const title = `Portfolio reporting smoke ${Date.now()}`;
  const viewName = `Smoke review queue ${testInfo.project.name}`;
  const created = await page.request.post(`${apiUrl}/requirements`, {
    data: { title, description: "Trace this requirement and its active clarification blockers." },
  });
  expect(created.ok()).toBeTruthy();
  const requirement = await created.json() as { id: string };
  expect((await postAnalysis(page, requirement.id)).ok()).toBeTruthy();

  await page.goto("/");
  await page.getByRole("searchbox", { name: "Search requirements" }).fill(title);
  await expect(page.getByText(title).first()).toBeVisible();
  // Saving and renaming a view lives behind the Views disclosure now; it is not
  // what the worklist is for, so it no longer occupies a band above it.
  const openSavedViews = () => page.locator("summary", { hasText: "Views" }).click();
  await openSavedViews();
  await page.getByLabel("View name").fill(viewName);
  await page.getByRole("button", { name: "Save current" }).click();
  await expect(page.getByLabel("Saved view")).toHaveValue(/.+/);

  await page.reload();
  await openSavedViews();
  await page.getByLabel("Saved view").selectOption({ label: viewName });
  await expect(page.getByRole("searchbox", { name: "Search requirements" })).toHaveValue(title);
  await expect(page.getByText(title).first()).toBeVisible();

  await page.goto(`/activity?requirement_id=${requirement.id}`);
  await expect(page.getByRole("heading", { name: "Activity" })).toBeVisible();
  if (testInfo.project.name === "chromium") {
    const sidebarBox = await page.locator(".app-sidebar").boundingBox();
    expect(sidebarBox).not.toBeNull();
    // main clears the fixed rail with padding rather than a margin, so the
    // comparison is against its content edge, not its border box.
    const contentStart = await page.locator("#main-content").evaluate((node) =>
      node.getBoundingClientRect().x + parseFloat(getComputedStyle(node).paddingLeft));
    expect(contentStart).toBeGreaterThanOrEqual(sidebarBox!.x + sidebarBox!.width);
  }
  const activity = page.getByRole("table", { name: "Activity, newest first" });
  await expect(activity.getByText(title).filter({ visible: true }).first()).toBeVisible();
  await expect(activity.getByText("Amina Owner").filter({ visible: true }).first()).toBeVisible();

  await page.goto("/reports?weeks=4");
  await expect(page.getByRole("heading", { name: "Reports" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Blocking now" })).toBeVisible();
  // The weekly numbers sit behind a disclosure under the chart; this week is the first row.
  await page.getByText("Weekly numbers, each linked to the activity it counts").click();
  const metric = page.getByRole("table", { name: /^Weekly counts/ })
    .getByRole("link", { name: /requirements? created, week of/ }).first();
  await metric.click();
  await expect(page).toHaveURL(/\/activity\?action=requirement_created/);

  await page.goto("/reports?weeks=4");
  const blocker = page.getByRole("table", { name: "Open blockers, oldest first" }).getByRole("link").first();
  await expect(blocker).toBeVisible();
  await blocker.click();
  await expect(page).toHaveURL(/\/requirements\/[^/]+\/clarify$/);
});
