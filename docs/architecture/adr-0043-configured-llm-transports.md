# ADR-0043 â€” Configured compatible model transports and isolated embedding generations

Status: Accepted by the user for the Direct Gemini integration enhancement.

The existing focused generation adapters already share structured-output behavior. Provider
selection must not require a new analyzer, Epic generator, Story generator or reviewer.

`LLM_CONFIG_PATH` opts into version 1 YAML profiles. Settings alone resolves environment-variable
credentials and validates selected task assignments at startup. The composition root constructs
one shared HTTP transport and the existing provider-neutral adapters. Supported tasks are
analysis, generation, review and knowledge; embeddings are selected independently. Credentials
are excluded from configuration serialization, safe summaries and fingerprints, and added to
the existing diagnostic redactor. Startup performs no model requests.

The compatible chat transport supports images, JSON Schema or JSON-object response modes,
configurable output-token parameters and bounded context/output budgets. Every completion is
validated locally before existing business-content and citation validation. Images are rejected
before transport when unsupported. Provider options cannot replace credentials, messages,
model selection or output contracts. OpenRouter routing retains no data collection, required
parameters and no provider fallback. Ollama's empty-content reasoning-response compatibility
is available only to its explicitly configured profile with reasoning disabled.

Each transport performs at most three attempts for rate-limit/server responses, with at most
ten seconds of backoff between attempts. Timeout, authentication, configuration, invalid-output
and availability failures remain distinct, safe application errors with existing job correlation
IDs. Timeouts are never retried automatically. Diagnostics record duration, attempt, token usage
when provided, and the nonsecret profile fingerprint. That fingerprint also scopes evidence
fragment caches. Existing fragments and generated artifacts remain durable.

Google embeddings use the native batch endpoint for explicit 768-dimensional output. Compatible
embedding endpoints use the shared transport. Count, order where supplied, dimensions and finite,
nonzero vectors are checked. Google vectors are normalized. Identity includes endpoint, protocol,
model, dimensions, normalization, provider request options and the preprocessing version; credentials do not identify vectors.

Profile mode uses separate knowledge-index generations, leaving legacy index tables intact.
Existing unidentified vectors are never used by a configured profile. Rebuilds resume a staging
generation for the same identity. Source-change counters guard each write; a short transaction
locks source changes and validates completeness before atomic activation. Previous generations
are retained. An index for a different identity fails explicitly instead of comparing vectors.
A stale source prevents activation and requires a resumed rebuild. Rollback activates a retained
generation only when its sources remain current. In-memory persistence implements the same
source-version and generation semantics and participates in transaction snapshots.

The operational CLI provides local configuration checking, explicit synthetic live checks,
resumable rebuild, index inspection and explicit activation/rollback. Operators stop accepting
requests and drain workers before changing profiles, perform checks/rebuild while stopped, then
restart. Launcher defaults respect profiles; an explicitly passed provider option conflicts with
profile selection and is rejected. With no profile path, legacy environment integration remains
available, including the offline fake provider.

Configuration-only switching covers supported chat-completions and embedding protocols. A
different wire protocol requires a transport adapter in the composition root. No application
operation is rewritten, no cross-provider fallback is added, and approved content is not regenerated.

### Embedded provider errors — 2026-09-18

The user's post-credit OpenRouter retry returned HTTP 200 with finish_reason=error and a
choice-level error code 429 after five successful packet/citation repairs. Google reported an
upstream model rate limit, leaving incomplete JSON content. Parsing that content mislabeled
the failure as malformed model output. Shared transports now inspect top-level and first-choice
errors before parsing content, including error finish reasons without details. Safe numeric code
classification preserves rate-limit/authentication/payment/configuration/unavailable failures;
unknown failures remain unavailable. Arbitrary provider messages are not public error text or
correction instructions. These failures never initiate citation correction, automatic saved-job
retry or provider fallback. Existing HTTP retry policy and request budgets are unchanged.
