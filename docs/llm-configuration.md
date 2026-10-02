# Model configuration and direct Gemini setup

Set `GEMINI_API_KEY` in the backend `.env` using a Google AI Studio key. Keep it out of YAML,
source control and the browser. The selected generation and embedding profiles both reference
that variable. Unselected example profiles do not require credentials.

The supplied `config/llm.yaml` selects `gemini-3.1-flash-lite` through Google's OpenAI-compatible
endpoint, JSON Schema with local validation, minimal reasoning, 8,192 output tokens and a
120-second request timeout. Embeddings use `gemini-embedding-001`, 768 dimensions and normalization.
Native Figma files/live links remain outside the attachment feature; exported images/PDFs are
processed by the existing source-document pipeline.

From the project root, using `.venv\Scripts\python.exe` on Windows:

```powershell
.venv\Scripts\python.exe -m smb_requirement_agent.interfaces.cli.llm check --config config/llm.yaml
.venv\Scripts\python.exe -m smb_requirement_agent.interfaces.cli.llm smoke --config config/llm.yaml
```

`check` validates local settings, selected credentials and limits without paid requests. `smoke`
explicitly sends synthetic structured-text requests to each distinct selected generation profile,
one blue image to the analysis profile and two embedding inputs. It fails if any check fails.
It does not send stored business requirements. Actual access depends on project quota/credits.

For a switch, stop the backend through its launcher so the existing graceful lifespan stops
accepting requests and drains workers. Keep the database and frontend intact. Apply migrations,
build the replacement index using the prospective configuration, and start the backend again:

```powershell
.venv\Scripts\python.exe -m smb_requirement_agent.infrastructure.persistence.migrate
.venv\Scripts\python.exe -m smb_requirement_agent.interfaces.cli.llm rebuild --config config/llm.yaml
```

After successful live checks and a complete index rebuild, set `LLM_CONFIG_PATH=config/llm.yaml`
in `.env` and run `start.ps1` without `-Provider`. Bash/CMD launchers work equivalently. An explicit
provider launcher option is rejected while a profile path is selected. Removing the profile path
returns to legacy provider environment settings. A legacy run uses its preserved legacy index;
it cannot read the new profile index. Normal startup prints each task's provider/model, never keys.

An interrupted rebuild leaves its staging generation and completed source versions intact. Run
the same rebuild command again to resume. Source changes during embedding or activation prevent
stale activation. Use `indexes --config config/llm.yaml` to inspect retained generations and
`activate --generation ID --config config/llm.yaml` for explicit rollback to a complete, current
generation. Restore the matching embedding profile before restarting. An identity mismatch
blocks knowledge search until the configured identity has a current active generation. Rebuild
commands require PostgreSQL; in-memory generations last only for the current process.

To switch to another supported service, edit `default`, optional `tasks` assignments and
`embedding` in YAML, set the named environment-variable credentials, run check/smoke/rebuild as
appropriate, and restart. Example profiles cover OpenAI, OpenRouter, Ollama and another compatible
endpoint. Task overrides use this shape:

```yaml
default: gemini-flash-lite
tasks:
  review: openai
  knowledge: gemini-flash-lite
  catalogue: gemini-flash-lite
embedding: gemini
```

The assignable tasks are `analysis`, `generation`, `review`, `knowledge` and `catalogue`. The
`catalogue` task reads uploaded architecture documents and proposes catalogue suggestions
(`infrastructure/llm/catalogue_extraction.py`, prompt `catalogue-extraction-v3`). Images
(PNG/JPEG diagrams and screenshots) need a profile with `images: true`; with a profile that cannot
read images, starting extraction on an image is refused with `catalogue_extraction_unsupported`
rather than silently skipped. The `local` provider follows `LOCAL_LLM_VISION_ENABLED`, and
`LLM_PROVIDER=fake` uses a deterministic extractor that reads labelled lines (`System:`,
`Capability: name (phrases)`, `Constraint:`, `A depends on B for reason`, and
`A sends X to B` as an inferred dependency).

The same `catalogue` model then checks names the catalogue does not know yet against a shortlist
of similar catalogue systems (`infrastructure/llm/catalogue_matching.py`, prompt
`catalogue-matching-v1`), and suggests which existing system each may be. The shortlist also
uses the configured embedding model; if that fails, it falls back to names alone with a warning.
A matching failure never fails the extraction. See ADR 0085.

Documents are read in as many calls as the model's context window needs. Each call's prompt is kept
below the input room the model has: `LOCAL_LLM_CONTEXT_WINDOW_TOKENS - LOCAL_LLM_MAX_OUTPUT_TOKENS`
for `local`, or `context_tokens - output_tokens` for the `catalogue` task's profile. OpenAI and
OpenRouter without profiles assume 100,000 tokens. Long passages are cut into parts whose citations
keep their location, such as `page 3 (part 2 of 3)`. A part the model cannot read becomes a warning
on the run; reading fails only when no part could be read. Local defaults (8,192 window, 4,096
reserved for output) work but need many calls. A 16k-context model such as `smb-qwen3-vl:8b-16k`
should set `LOCAL_LLM_CONTEXT_WINDOW_TOKENS=16384` in both the model server and the application.
If a window is too small to hold even the instructions, reading is refused with
`catalogue_extraction_unsupported`.

Generation profile fields: `provider`, `endpoint`, `model`, `api_key_env`, `images`,
`structured_output` (`json_schema`/`json_object`), `context_tokens`, `output_tokens`,
`output_parameter` (`max_tokens`/`max_completion_tokens`), `reasoning_effort`, `timeout_seconds`,
`request_options`, and the Ollama-only compatibility flag. `request_options.extra_body` adds
provider-specific request properties after safety validation. It cannot replace application-owned
properties. Automatic provider fallback is prohibited. Configure image support accurately:
the application refuses unsupported visual input rather than dropping it.

Embedding profiles use `protocol` (`compatible`/`google`), endpoint/model/credential reference,
768 dimensions, normalization, preprocessing version, batch size and timeout. Ollama can omit the
dimensions request parameter, but its returned vectors must still have exactly 768 finite values.
Changing embedding identity requires a separate index generation; changing generation settings
changes diagnostics and evidence-cache identity. Existing approvals, attachments, citations and
generated artifacts are retained.

Safe job failures distinguish timeout, rate limit, authentication, request configuration and invalid
output. Provider response bodies are not logged or returned to the browser. Check AI Studio's
project quota/credits when Google returns resource exhaustion. No billing changes or automatic
provider switches are performed by the application.

Protocol references: [Google compatibility](https://ai.google.dev/gemini-api/docs/openai),
[Google embeddings](https://ai.google.dev/gemini-api/docs/embeddings).

Architecture mapping uses the same configuration (ADR-0082). The `knowledge` task's model selects
impacted systems for features, stories and the catalogue page's preview, within the same input
room rules as above; when the catalogue is too large for a small window, the systems the text
names are offered first and the rest are reported as not offered. The architecture evidence index
is embedded with the configured embedding (the profile's `embedding`, or the provider's embedding
model), so there is no separate architecture model server or tokenizer file. An index records the
embedding model it was built with: after changing it, build and publish the architecture catalogue
again before mapping resumes.
