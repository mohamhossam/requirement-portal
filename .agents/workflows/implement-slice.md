---
description: Implement one approved roadmap slice without leaking future-slice scope.
---

# Implement Roadmap Slice

1. Read `AGENTS.md`, `ROADMAP.md`, and `WORKSPACE.md`.
2. Identify the requested slice.
3. Create or update `docs/slices/slice-XX-<slug>.md`.
4. List in-scope and explicitly out-of-scope behavior.
5. Inspect current code/tests.
6. Implement the smallest end-to-end slice:
   - Domain
   - Application
   - Port if required
   - Adapter if required
   - API/UI if required
   - Tests
7. Do not implement later slices.
8. Run:
   - pytest
   - ruff check .
   - ruff format --check .
   - mypy src tests
   - lint-imports
9. Update slice validation evidence.
10. Report implemented behavior, architecture impact, validation, and deferred items.
