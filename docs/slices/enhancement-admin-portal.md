# Enhancement — Administration portal (configuration, AI models, system prompts, users and roles)

> Status: **planned; not started.** Decisions recorded 2026-09-26; system-prompt
> decisions (8–11, sub-slice F) recorded 2026-09-28. Implementation must not
> begin until this spec (or its first sub-slice) is scheduled in `ROADMAP.md`.
> Delivered as six sub-slices, A–F, each independently shippable.

## Objective

Administrators manage the application from inside it:
- see the system's health and its effective configuration;
- change the operational settings that are safe to change while running;
- manage AI model profiles;
- manage the AI system prompts;
- grant and revoke access through Keycloak groups;
- reassign Requirement ownership when people leave.

Every change is validated, attributed, reasoned and reversible.

## User Outcome

- A configuration administrator raises the provider rate limit, sees it
  applied on every API and worker process within seconds, and can roll it back
  from the setting's history.
- They prepare a new AI model profile, validate it, and activate it with the
  index rebuild it needs, without editing files on the server.
- They edit the Story generation system prompt, validate it, optionally
  smoke-test it, and activate it. Every process uses it within seconds, and new
  Stories show the new prompt version in their provenance. If the results are
  worse, they roll back or reset to the built-in prompt.
- An access administrator finds a colleague in Active Directory, grants them
  access and the knowledge-maintainer role, and later signs them out
  everywhere.
- When an owner leaves, the access administrator hands their Requirements to
  someone else, with the reason recorded.

## Recorded decisions

| # | Question | Decision |
|---|---|---|
| 1 | Scope of "all configuration" | Four tiers. Tier 1 (live settings) and Tier 2 (AI models) are editable; Tier 3 (startup-only) and Tier 4 (secrets) are visible but not editable. Start simple; staging Tier 3 edits for the next restart can come later |
| 2 | Environment versus portal for Tier 1 | The environment value is the default; a portal change overrides it; "reset to default" removes the override |
| 3 | Secrets | Stay in the environment or secret store. The portal shows only whether each is present, never the value |
| 4 | Admin roles | Two: `config_admin` (settings, AI models) and `access_admin` (users, groups, Requirement ownership) |
| 5 | AI model management | Included (sub-slice D) |
| 6 | Requirement ownership administration | Included (sub-slice E) |
| 7 | Roles and groups | Admins assign only the fixed set the application understands; they cannot create roles or groups |
| 8 | System prompt scope | Full text per AI operation, guarded. The built-in text is the default. A code-owned guard (untrusted input, no invention, output contract) is always appended and cannot be edited |
| 9 | Who edits prompts | `config_admin`; no new role or group |
| 10 | When a prompt change applies | Live, within seconds on every process, like Tier 1 settings; no restart |
| 11 | Gate before activation | Validation always; a smoke test is optional |

## Current state (as found)

- **Settings:** every setting is an environment variable resolved once, at
  startup, into a frozen `Settings` dataclass (`infrastructure/config/settings.py`,
  about 90 fields). Values are passed into constructors while the object graph
  is built. `AGENTS.md` §4.5 makes this a rule.
- **AI models:** profiles live in `config/llm.yaml` (`LLM_CONFIG_PATH`). They are
  validated by `LLMProfileConfiguration` and operated through the
  `interfaces.cli.llm` commands `check`, `smoke`, `rebuild`, `indexes` and
  `activate`. A switch means a documented stop, rebuild and restart
  procedure (`docs/llm-configuration.md`).
- **Prompts:** system prompts are Python constants in
  `infrastructure/llm/prompts/` (analysis and its focused recovery passes,
  Epic, Feature, Story, Story quality, knowledge screening and suggestions,
  and the shared `GENERATION_RULES`), plus one inline prompt in
  `infrastructure/architecture/reasoning.py`. Each module has a
  `PROMPT_VERSION`, recorded as `prompt_version` in the provenance of generated
  content (`AGENTS.md` §7.14). `AGENTS.md` §7.8 already treats prompts as
  replaceable configuration, but changing one today needs a code release.
- **Roles:** the application enforces `knowledge_reader` and
  `knowledge_maintainer`. Enhancement 8A.2 moves roles into Keycloak client
  roles granted through groups, with users federated from Active Directory.
- **Ownership:** `RequirementAccess.transfer`, `assign_reviewer` and
  `remove_reviewer` all begin with `require_owner`. Only the current owner can
  change access, so a departed owner's Requirements cannot be reassigned today.
- **Known actors:** the directory lists only people who have signed in (ADR-0018).
- **UI:** there is no administration area.

## Configuration tiers

| Tier | Source of truth | Portal | When a change applies |
|---|---|---|---|
| 1 Live | Environment default, plus an optional database override | Edit, reset to default, history, rollback | Within seconds on every process, with no restart |
| 2 AI models | Database (imported once from `config/llm.yaml`) | Draft, validate, smoke-test, activate, roll back | At the next API and worker restart; embedding changes need a completed index rebuild first |
| Prompts | Built-in code default, plus an optional versioned database override | Draft, validate, optional smoke test, activate, reset to built-in, roll back | Within seconds on every process, for new AI calls; calls already running keep their version |
| 3 Startup-only | Environment | Read-only, with the value's source (environment or default) and how to change it | Deployment change and restart |
| 4 Secrets | Environment or secret store | Presence only (configured, missing, last validated) | Deployment change and restart |

**Initial Tier 1 catalogue.** Each entry must be confirmed to be read when
used, not captured at startup, or its consumer changed to read through the
runtime-settings port:
- `PROVIDER_RATE_LIMIT_PER_MINUTE`;
- `NOTIFICATION_RETENTION_DAYS`;
- `DOCUMENT_MAX_FILE_BYTES`, capped by the deployment's fixed upload ceiling
  (nginx `client_max_body_size`); the portal refuses values above it and says
  why;
- `DOCUMENT_CONTEXT_MAX_CHARACTERS`;
- the document extraction limits: `DOCUMENT_MAX_PDF_PAGES`,
  `DOCUMENT_MAX_EXTRACTED_CHARACTERS`, `DOCUMENT_MAX_XML_NODES`,
  `DOCUMENT_MAX_IMAGE_PIXELS`, `DOCUMENT_MAX_SPREADSHEET_CELLS` and
  `DOCUMENT_EXTRACTION_TIMEOUT_SECONDS`;
- `LOG_LEVEL`;
- `OIDC_PASSWORD_LOGIN_LABEL` (from 8A.2);
- `KNOWLEDGE_EVALUATION_APPROVED`: Tier 1 if it only gates at request time,
  otherwise Tier 3.

Everything else is Tier 3 or Tier 4. **`DEBUG_TRACE_ENABLED` is never
portal-editable**, because it writes Requirement text to disk. Worker
concurrency, pool sizes, identity, persistence, metrics and log format stay
Tier 3.

## Roles

| Client role (on `requirement-api`) | Keycloak group | Grants |
|---|---|---|
| `config_admin` | `requirement-ai-config-admins` | Overview, effective configuration, Tier 1 settings, AI models, system prompts, audit log (read) |
| `access_admin` | `requirement-ai-access-admins` | Overview, users and access, Requirement ownership, audit log (read) |

- Both admin groups also carry `app_user`.
- Self-protection:
  - an access administrator cannot remove their own `access_admin`;
  - removing the last `access_admin` is refused.

  Keycloak's `master`-realm emergency administrator remains the break-glass
  path.
- Fake identity adds a persona, `fake-admin` ("Ada Admin"), holding both admin
  roles and `app_user`, so every admin path works offline.

## Sub-slices

### A — Foundation (read-only)

- The admin roles, both in Keycloak (depends on 8A.2) and in fake identity.
- An **Administration** area in the app, visible only to admins, at `/admin`.
- **Overview:**
  - readiness (`/ready`), release, and uptime per process;
  - background worker health;
  - AI job queue counts;
  - links to Grafana, Graylog and the Keycloak admin console, configured by new
    optional Tier 3 variables: `ADMIN_LINK_GRAFANA_URL`,
    `ADMIN_LINK_GRAYLOG_URL` and `ADMIN_LINK_KEYCLOAK_URL`.
- **Effective configuration:** every setting, grouped by category, with its tier,
  value (secrets shown only as present or missing), source, and a description
  taken from `.env.example`.
- **Audit log:** an append-only store of admin actions, and a read screen with
  filters. From sub-slice A on, every admin mutation writes an entry
  containing:
  - the actor;
  - the time;
  - the action;
  - the target;
  - before and after (secret-free);
  - a mandatory reason;
  - the correlation ID.

  When the Graylog slice is present, entries are also logged to the security
  stream.
- **Process registry:** each API and worker process records a heartbeat with
  its service, start time, applied settings version and AI profile version. The
  portal uses it to show what each process is running.

### B — Live settings (Tier 1)

- A runtime-settings store: current overrides and full history, with version
  numbers.
- An application port, `RuntimeSettingsPort`, gives consumers the current
  effective value: the override, else the startup default.
- Each process refreshes its snapshot on a short interval (a Tier 3 setting,
  default 5 seconds) and reports the applied version in the process registry.
  Memory persistence keeps the store in-process.
- Edits:
  - validated with the same rules as startup (`settings_validation.py`), plus
    per-setting bounds;
  - the portal shows a before/after comparison and asks for confirmation;
  - optimistic concurrency, so two admins cannot silently overwrite each
    other;
  - a mandatory reason.
- Reset to default removes the override. Rollback re-applies a historical value
  as a new version.
- The portal shows "applied on N of M processes" after each change.

### C — Users and access (depends on 8A.2)

- An `AccessDirectoryPort` with two adapters:
  - Keycloak, through the admin REST API, using a dedicated confidential
    client `requirement-admin-api` (client-credentials). Its secret,
    `KEYCLOAK_ADMIN_CLIENT_SECRET`, is Tier 4. Its admin permissions are
    limited to searching and viewing users, managing membership of the five
    application groups, and signing out users' sessions. Confirm how Keycloak
    26 fine-grained admin permissions express this at implementation.
  - A deterministic fake, for offline development.
- **Screens:**
  - search users (Keycloak searches the federated AD, so people who have
    never signed in are found);
  - a user's groups, roles, last sign-in and active sessions;
  - add or remove membership of the five fixed groups;
  - sign out all sessions;
  - members per group.
- **Not possible:** creating users, editing AD attributes, resetting passwords,
  or creating roles or groups (decision 7). AD and Keycloak own these.
- The browser never receives a Keycloak admin token. All calls go through the
  API, with authorization in the application layer (ADR-0018, ADR-0078).

### D — AI model management (Tier 2)

- Profiles move from `config/llm.yaml` into a versioned database store, imported
  once from the file. `LLMProfileConfiguration` remains the validation model.
  - With the store in use, the file is no longer read, and `LLM_CONFIG_PATH`
    becomes the import source only.
  - Legacy `LLM_PROVIDER` modes and the fake provider are unchanged.
- **Lifecycle:** draft, then validate, then optional smoke test, then activate.
  - **Validate:** the existing `check` logic. No paid requests. Reports which
    `api_key_env` secrets are present on each process.
  - **Smoke test:** the existing `smoke` logic. It sends synthetic requests
    only, requires explicit confirmation, and counts against the provider rate
    limit (added to `tests/architecture/test_provider_rate_limit.py`).
  - **Activate:**
    - records the active version;
    - applies at the next API and worker restart;
    - the portal shows each process's running version and "restart pending".
    - Hot-swapping models without a restart is deliberately out of scope
      (decision 1: start simple).
  - **Embedding profile changes** run the existing rebuild as a tracked job,
    with progress, resume and retry; they require PostgreSQL. Activation is
    allowed only once the new index generation is complete. Rollback uses the
    existing generation `activate`.
- Profile fields are edited in structured forms, not raw YAML. The rule
  forbidding automatic provider fallback, and `request_options` safety
  validation, are unchanged.

### E — Requirement ownership administration

- **Domain:** add administrative variants of transfer, reviewer assignment and
  reviewer removal to `RequirementAccess`.
  - They skip `require_owner`, but require an administrator actor and a
    non-empty reason.
  - They keep every existing invariant: one owner; the owner is never a
    reviewer.
  - They record a new change kind, `ADMIN_REASSIGNED`, with the administrator's
    snapshot and the reason, so the Requirement's access history and revisions
    show the intervention.
- **Application:** an `AdministerRequirementAccess` use case, authorized for
  `access_admin`, with optimistic concurrency on the access version.
- **Target people:** the target must hold `app_user`. If they have never signed
  in, their actor profile is registered from the Keycloak directory entry,
  using the same issuer and subject derivation (ADR-0018), so ownership belongs
  to the identity they will sign in with.
- **Screens:**
  - find a person's owned and reviewing Requirements;
  - bulk-reassign ownership from one person to another, with a reason;
  - add or remove reviewers.
- Draft ownership stays fixed until promotion (out of scope).

### F — System prompts (decisions 8–11; needs A and B)

- **Prompt catalogue.** Application-level metadata, with one slot per AI
  operation:
  - requirement analysis, and its focused passes: desired-outcome review,
    clarification review, question-reconciliation recovery, citation recovery,
    and uncertainty-rationale recovery;
  - Epic, Feature and Story generation, and the shared generation rules;
  - Story quality evaluation;
  - knowledge relationship screening and clarification suggestions;
  - architecture impact reasoning.

  Each slot has a key, its operation, and its built-in text and version (the
  current code constant). User-prompt builders and output schemas stay in code
  and are not editable.
- **Guarded composition (decision 8).** Each built-in prompt is split into an
  **editable body** and a **locked application guard**. The guard holds the
  rules that code validation or safety depends on:
  - untrusted-input and prompt-injection rules;
  - the no-invention rules (facts versus assumptions, no invented numbers,
    policies or ownership);
  - no empty or whitespace-only entries;
  - stable-ID and question-reconciliation rules;
  - the structured-output contract.

  The composed system prompt is the body followed by the guard, and the guard
  states that it takes precedence. The split for each slot is decided and
  reviewed at implementation. With no override, the composed prompt must equal
  today's text, so behaviour does not change.
- **Lifecycle:**
  - **Draft:** edit the body in the portal.
  - **Validate:** no paid requests. The body is not blank, fits a character
    budget derived from the active model profile's input budget, and does not
    copy or contradict the guard markers.
  - **Smoke test (optional, decision 11):** the existing `smoke` logic, run on
    synthetic input with the active model profile after explicit confirmation.
    It shows the parsed output and counts against the provider rate limit.
  - **Activate:** records a new active version for the slot.
  - **Reset to built-in:** removes the override.
  - **Roll back:** re-applies a historical version as a new version.

  Every mutation uses optimistic concurrency and needs a mandatory reason.
- **Live application (decision 10).** A `SystemPromptPort` resolves the
  effective prompt for a slot: the active override, else the built-in. Each
  process keeps a snapshot, refreshed by B's refresh loop, and reports its
  applied prompt-set version in the process registry. The portal shows
  "applied on N of M processes". A call already running keeps the version it
  started with. The OpenAI, local and OpenRouter adapters all read through the
  port; fake adapters are unchanged.
- **Provenance.** With an override active, the recorded `prompt_version` is
  `<built-in version>+admin.<n>`, for example `story-v5+admin.3`. This uses the
  existing field; no payload or schema change. The store keeps the full text of
  every version, so a reviewer can see exactly which prompt produced a result.
- **Built-in upgrades.** When a release ships a newer built-in version for a
  slot that has an active override, the override stays active and is flagged
  "based on an older built-in". The portal shows the old built-in, the new
  built-in and the override side by side, so the admin can re-base or reset.
  Nothing changes silently.
- **Screens:**
  - a slot list with status: built-in, override active, or outdated base;
  - an editor with a diff against the built-in, and the locked guard shown
    read-only;
  - version history, with author, reason and time;
  - the smoke-test result panel.

## Out of Scope

- Editing Tier 3 settings, or staging them for the next restart (decision 1:
  later).
- Setting or displaying secret values.
- Hot-swapping AI models without a restart.
- Creating users, roles or groups, or editing AD attributes or passwords.
- Reassigning draft ownership.
- Multi-tenant or per-team administration.
- Changing `DEBUG_TRACE_ENABLED` from the portal.
- Editing the locked prompt guard, user-prompt templates or output schemas.
- System prompts per team, per Requirement or per model profile.
- A/B testing of prompts, and automatic evaluation gating of prompt changes
  (the smoke test stays optional).

## Domain

- `RequirementAccess`: administrative transfer and reviewer changes, and the
  `ADMIN_REASSIGNED` change kind (sub-slice E).
- New value objects for admin audit entries and runtime-setting versions. The
  runtime-settings catalogue itself is application-level metadata.
- A system-prompt version value object: slot, version number, body, the
  built-in version it was based on, author, reason and time (sub-slice F). The
  prompt catalogue and its guards are application-level metadata.

## Application Use Cases

- `GetSystemOverview`, `GetEffectiveConfiguration` and `ListAdminAudit` (A).
- `UpdateRuntimeSetting`, `ResetRuntimeSetting`, `RollbackRuntimeSetting` and
  `ListRuntimeSettingHistory` (B).
- `SearchDirectoryUsers`, `GetUserAccess`, `ChangeGroupMembership` and
  `SignOutUser` (C).
- `SaveModelProfileDraft`, `ValidateModelProfiles`, `SmokeTestModelProfiles`,
  `ActivateModelProfiles`, `StartEmbeddingRebuild` and
  `RollbackModelProfiles` (D).
- `AdministerRequirementAccess` and `ListActorAssignments` (E).
- `ListSystemPrompts`, `GetSystemPromptHistory`, `SaveSystemPromptDraft`,
  `ValidateSystemPrompt`, `SmokeTestSystemPrompt`, `ActivateSystemPrompt`,
  `ResetSystemPrompt` and `RollbackSystemPrompt` (F).
- Every mutation authorizes `config_admin` or `access_admin` in the application
  layer and writes an audit entry in the same transaction.

## Ports

- `RuntimeSettingsPort`, `AdminAuditPort`, `ProcessRegistryPort`,
  `AccessDirectoryPort`, `ModelProfileStorePort`, `SystemPromptPort` (effective
  prompt per slot) and `SystemPromptStorePort` (versions), each with PostgreSQL
  (or Keycloak) and in-memory or fake adapters.

## Adapters

- PostgreSQL adapters and migrations (timestamped names) for runtime settings
  and history, admin audit, process registry, model profile versions and
  system-prompt versions.
- A Keycloak admin REST adapter and a fake directory adapter.
- The settings refresh loop and process heartbeat, run by the API and worker
  processes. The same loop refreshes the system-prompt snapshot.
- The OpenAI, local and OpenRouter LLM adapters take their system prompts from
  `SystemPromptPort` instead of importing the prompt constants directly.

## API

- `/admin/...` routes: overview, configuration, settings, models, prompts,
  users, groups, ownership and audit.
- All require authentication. Authorization happens in use cases; the OpenAPI
  contract and the generated TypeScript types are regenerated.
- The model and prompt smoke tests and the embedding rebuild use the provider
  rate limit.

## UI

- An **Administration** navigation item and routes (`/admin`, `/admin/settings`,
  `/admin/models`, `/admin/prompts`, `/admin/users`, `/admin/ownership`,
  `/admin/audit`), shown only to admins. Sections are hidden by role.
- Governed by `docs/ux-plan.md` and `docs/design-system.md`, and WCAG 2.2 AA.
  Confirmation dialogs for destructive or wide-reaching changes; clear tier
  badges; "applied on N of M processes" and "restart pending" states; a
  mandatory reason field on every change.
- **Note for scheduling:** the portal needs new API client code, hooks and
  state. That is feature work, outside the redesign's presentation-only rule
  in `CLAUDE.md`, so this slice must be explicitly scheduled rather than folded
  into redesign phases.

## Business Rules

- Only `config_admin` changes settings, AI models and system prompts. Only
  `access_admin` changes access and ownership. Both can read the overview and
  the audit log.
- Every admin mutation is audited, with the actor, a mandatory reason and
  before/after. Audit entries are never edited or deleted by the application.
- Secrets are never returned by any API or shown in the portal.
- A Tier 1 value is valid under the same rules as at startup. An invalid value
  is refused, never partially applied.
- A portal override always wins over the environment default, until it is
  reset.
- An embedding profile cannot be activated before its index generation is
  complete. No automatic provider fallback.
- Administrative ownership changes preserve all access invariants and are
  visible in the Requirement's access history and revisions.
- An access administrator cannot remove their own `access_admin`, and the last
  `access_admin` cannot be removed.
- Only the fixed application groups can be managed; no role or group creation.
- The locked prompt guard is always part of the composed system prompt and
  cannot be edited or removed from the portal.
- An invalid prompt body is refused, never partly applied. A prompt override
  wins over the built-in until it is reset.
- Every AI result records the exact prompt version that produced it, including
  the override number.
- Prompt text is not a secret: the audit entry keeps the full before/after
  text.

## Tests

- **Domain:**
  - administrative transfer and reviewer changes: invariants hold, a reason is
    required, the change kind and snapshots are recorded;
  - a non-admin cannot use them.
- **Application, per use case:**
  - authorization for each role and the refusal for others;
  - an audit entry in the same transaction;
  - optimistic-concurrency conflicts;
  - validation refusals.
- **Runtime settings:**
  - precedence (override, else environment, else default);
  - reset and rollback;
  - refresh propagates within the interval;
  - an invalid value is never applied;
  - the process registry reports the applied version.
- **Catalogue guard:** every Tier 1 key maps to a real setting, and a
  consumer reads it through the port. `DEBUG_TRACE_ENABLED` and every secret
  are excluded (an architecture test).
- **Secrets guard:** no admin API response contains a Tier 4 value (an
  architecture test over response schemas and a runtime check).
- **Access directory:**
  - the fake adapter drives the application tests;
  - the Keycloak adapter is contract-tested against a recorded or local
    Keycloak;
  - the membership rules (fixed groups, self-protection, last admin) hold.
- **Model profiles:**
  - import from `config/llm.yaml` is lossless;
  - validate, then smoke (with the fake provider), then activate;
  - an embedding change is blocked until its rebuild job completes;
  - rollback works;
  - the smoke route is in the provider rate-limit list.
- **System prompts:**
  - for every slot and every real adapter, the guard is present and comes
    after the body;
  - with no override, the composed prompt equals today's built-in text;
  - precedence, reset and rollback;
  - refresh propagates within the interval, and the process registry reports
    the applied prompt-set version;
  - provenance carries the `+admin.<n>` suffix while an override is active;
  - an override is flagged when its base built-in version changes;
  - validation refusals (blank, over budget, guard markers);
  - the prompt smoke route is in the provider rate-limit list;
  - an architecture test: LLM adapters get system prompts only through
    `SystemPromptPort`.
- **API:** role-based 403s, contract snapshots, OpenAPI and type
  synchronization.
- **Frontend:**
  - component tests for every screen and state, including an
    accessibility check;
  - Playwright journeys for config admin (change and roll back a live
    setting; edit, activate and roll back a system prompt), access admin (grant and revoke access in fake mode, reassign
    ownership) and a non-admin (no Administration item, direct URL refused).

## Acceptance Criteria

- [ ] Admins see an Administration area; others do not, and admin APIs refuse them.
- [ ] The overview shows readiness, per-process versions, worker health, the job queue and operator links.
- [ ] The effective configuration lists every setting with tier and source; secrets show only presence.
- [ ] A Tier 1 change applies on all processes within the refresh interval, and can be reset or rolled back.
- [ ] AI model profiles can be drafted, validated, smoke-tested, activated and rolled back; embedding changes are gated on a completed rebuild.
- [ ] Config administrators draft, validate, optionally smoke-test, activate, reset and roll back system prompts; changes apply live on every process, generated content records the prompt version, and the locked guard cannot be removed.
- [ ] Access administrators find AD users through Keycloak, manage membership of the fixed groups, and sign users out; self-lockout and last-admin removal are refused.
- [ ] Access administrators reassign a departed owner's Requirements and manage reviewers, with the reason visible in access history.
- [ ] Every admin mutation appears in the audit log with actor, reason and before/after.
- [ ] Everything works offline with fake identity and memory persistence, except the rebuild job, which requires PostgreSQL.
- [ ] All backend and frontend quality gates and CI are green.

## Dependencies

- **Enhancement 8A.2** (AD sign-in, Keycloak roles) for the Keycloak side of
  sub-slices A and C. The fake paths work without it.
- **Centralized logging** (Graylog) is optional; when present, audit entries are
  also logged to the security stream.
- A new ADR amending `AGENTS.md` §4.5:
  - startup settings remain environment-only and resolved once;
  - a catalogued set of runtime policy settings is application data, served
    through `RuntimeSettingsPort` with environment defaults;
  - AI model profiles move to a versioned store;
  - system prompt bodies become versioned application data, with code-owned
    built-in defaults and a locked guard (consistent with `AGENTS.md` §7.8 and
    §7.14).

## Suggested delivery order

A, then B, then F (it needs A's audit log and B's refresh loop), then E, then C
(once 8A.2 is in), then D. Each sub-slice gets its own validation evidence
below.

## Validation Evidence

None yet; not started.
