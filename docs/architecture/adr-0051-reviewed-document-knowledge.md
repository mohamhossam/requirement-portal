# ADR-0051: Reviewed document knowledge

Status: Accepted direction from the user's detailed ingestion/retrieval implementation request.
Delivery and release qualification remain tracked in the enhancement specification.

Standalone reference documents have independent identity, owner, immutable uploaded bytes,
append-only extraction revisions and content-bound publication approval. No fake Requirement is
created to host a library upload. PostgreSQL stores bytes through the existing blob port.

An owner explicitly includes or excludes each block. A selected corrected passage is identified
by file version, extraction revision, approval fingerprint and original block location. Approval
does not assert applicability to other Requirements. Unapproved versions and excluded passages
are private. Shared views expose only approved selected text; full original downloads remain
owner-only because they can contain excluded material.

A separate bounded document worker claims durable ingestion attempts. Stale/cancelled attempts
cannot commit. Local malware scanning fails closed. The explicitly named offline scanner is
restricted to fake identity and memory persistence and is not malware protection. OCR uses local
Docling/Tesseract with pre-provisioned model assets, never a remote interpretation service.

Embedding and lexical batches are durably staged with an embedding/chunking identity, invisible
to search until complete publication activation in one transaction. A prior published version remains eligible while
its replacement is processed. Withdrawal immediately removes its live search eligibility while
retaining history. Search revalidates approved text and publication after candidate retrieval.

The current conservative UTF-8 byte counter is an explicit, identity-versioned token-budget
adapter, not a model-token count or an English character estimate. Model-matched tokenization,
chunk-size benchmarking and production retrieval quality are qualification work; no quality or
capacity target follows from that default.

Existing Requirement attachment, full evidence packet and bilateral conflict workflows stay
separate. Integrating reference applicability proposals must not silently promote retrieved
policy statements into confirmed facts.
