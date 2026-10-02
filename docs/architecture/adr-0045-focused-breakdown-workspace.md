# ADR-0045 — Focused Breakdown workspace

Status: Accepted
Date: 2026-09-18

## Context

The expanded workspace displayed administration, every backlog level and every quality
report together. Existing Epic, Feature and Story routes did not select a focused item.
The approved maintenance plan retains the existing contracts and governance rules.

## Decision

Compose a Breakdown-specific shell with a 280px backlog navigator and route-selected
detail. Source and People use native modal drawers; History and final review retain
their existing routes. Other requirement stages retain the default shell.

Keep keyed artifact editors mounted within the current actor/requirement workspace,
hiding unselected detail. This preserves unsaved drafts and existing version-conflict
reconciliation. The workspace remounts when actor or requirement changes. Drafts are
not persisted beyond that workspace lifetime.

Enable Story queries only for selected or explicitly expanded Features, and quality
and proposal reads only for the selected Feature/Story view. Disabled views keep
actor-scoped cached data. The existing requirement jobs provider remains the sole
polling owner. Cache start/retry input targets to identify the affected item without
adding server response fields. Historical jobs without a known target remain labelled
by operation.

## Consequences

Navigation uses existing URLs, including refresh and browser history. Hidden editor
instances use some memory but make no extra polling or disabled data requests.
Native drawers provide modal background isolation; focus restoration and tab trapping
are tested. Applied changes that remove an observed selected Story return to its parent.
No domain, application, infrastructure, API, persistence or provider contracts change.
Approval and publication rules from ADR-0021 remain authoritative.
