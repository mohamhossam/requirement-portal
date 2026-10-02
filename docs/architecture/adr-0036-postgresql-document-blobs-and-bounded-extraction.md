# ADR-0036: PostgreSQL document blobs and bounded extraction

## Status

Accepted

## Context

Durable metadata referenced process-local files and in-process parsing could consume unbounded CPU,
memory, or parser work.

## Decision

PostgreSQL stores immutable bytes in a dedicated table keyed by document-version ID with checksum
and byte count. Blob and metadata writes share a transaction; revision JSON contains metadata only.
Memory mode retains an in-memory blob adapter. Durable runtime filesystem fallback is removed after
the maintenance import.

Extraction runs in spawned child processes with defaults of two active processes, four waiting
requests, a 30-second deadline, and 512 MiB per child. Parsers enforce 200 PDF pages, 1,000,000
characters, 250,000 XML nodes, 20 million image pixels, and 1,000,000 visited spreadsheet cells.

## Consequences

Migration must import blobs referenced by current or historical metadata and verify every checksum
before the new application opens for writes. Saturation and limit failures are explicit retryable
or caller-visible errors.
