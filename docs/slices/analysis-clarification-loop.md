# Analysis Clarification Loop

The loop now has an explicit completion state. Saving any subset of answers
immediately re-runs analysis with all saved human clarifications. New uncertainty
is rendered as the next answer round. When and only when no unresolved item
remains, the Requirement Owner can select **Confirm analysis**. Re-analysis,
new answers, or a requirement edit revokes that confirmation; PostgreSQL
revision history preserves the prior state.

## Objective
Repair the delivered Slice 2 / Slice 4A analysis workflow so a reviewer can answer
AI-raised uncertainties and re-analyse the same requirement. This does not start Slice 5.

## User Outcome
A reviewer can answer any subset of assumptions, open questions, ambiguities, or
potential dependencies. Answers are retained as human-provided confirmed context,
used by the next analysis, and shown separately from AI extraction.

## In Scope
- Reduce repetitive unresolved output through prompt prioritisation and a combined cap.
- Capture, validate, and retain human clarification answers.
- Re-run analysis for the same requirement with those answers.
- Make every item currently shown under `Needs confirmation` actionable in the UI.

## Out of Scope
- Story generation from Slice 5.
- Final blocker resolution and approval policy from Slices 8 and 9.
- Durable persistence/version history from Slice 10.

## Domain
- `ClarificationKind` identifies the uncertainty category.
- `HumanClarification` preserves the original subject and human answer.
- `RequirementAnalysis` carries clarifications separately from extracted facts.
- Analysis value objects move to `domain/analysis/value_objects.py`.

## Application Use Cases
- `ClarifyRequirementAnalysis` validates answers and regenerates with human context.
- `AnalyzeRequirement` preserves prior clarifications during ordinary re-analysis.

## Ports
- `RequirementAnalyzerPort` receives provider-independent human clarifications.

## Adapters
- Fake, OpenAI, and local analyzers consume clarifications.
- Epic and Feature prompts receive confirmed clarifications downstream.
- If local analysis returns no uncertainty for a requirement containing undefined
  qualifiers, a compact clarification-only operation generates 1–12 focused questions.

## API
- `POST /requirements/{id}/analysis/clarifications`.
- Analysis responses include `clarifications`.
- Outdated answers return `409`; invalid input returns `422`.

## UI
- Every unresolved item has an optional answer field.
- Any non-empty subset can be submitted with `Save answers and re-analyse`.
- Saved answers appear under `Human-provided clarifications`.

## Business Rules
- A human answer is confirmed context, not a fact extracted from the requirement.
- An answer must reference an uncertainty in the current analysis.
- Unanswered items remain unresolved.
- The prompt consolidates overlap and requests at most 12 unresolved items combined.
- Clarification analysis is always a complete replacement, not a delta. The local adapter
  retries once with an explicit completeness reminder if the first result is empty.
- Undefined qualifiers such as `valid`, `sufficient`, `fraud`, or `AML` cannot silently
  pass as implementation-ready when no clarification has been provided.

## Tests
- Domain invariants and unresolved keys.
- Use-case preservation, regeneration, and stale-answer conflict.
- API response/error behavior and adapter contracts.
- UI partial-answer submission and human/AI separation.

## Acceptance Criteria
- [x] A reviewer can answer one or more displayed uncertainty items.
- [x] Submission re-analyzes the same requirement.
- [x] Saved answers remain visibly human-owned.
- [x] Resolved subjects leave the displayed uncertainty list.
- [x] Outdated submissions cannot answer a different current analysis.
- [x] All affected vertical-slice fields are delivered.

## Validation Evidence
- `pytest` — PASS, 268 tests.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS, 147 files formatted.
- `mypy src tests` — PASS, 120 source files.
- `lint-imports` — PASS, 2 contracts kept.
- `npm.cmd test -- --run` — PASS, 19 tests.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run lint` — PASS.
- `npm.cmd run api:check` — PASS.
- `npm.cmd run build` — PASS, production bundle generated.
- Browser visual click-through — NOT RUN; no browser connection was available in this session.
- Isolated live Ollama clarification flow — PASS with the previously failing requirement;
  3 answers saved and a complete refreshed analysis returned.
- Isolated live Ollama initial analysis — PASS with the current banking requirement;
  6 focused confirmation questions returned after the primary analysis returned zero.

## Deferred
- Analysis-wide generation provenance remains registered debt for before Slice 9.
- Clarification timestamps and durable history remain in later governance/persistence.
- Durable requirement memory and context-budget policy await an explicit persistence scope
  decision; the current Ollama process exposes a 4,096-token context window.
