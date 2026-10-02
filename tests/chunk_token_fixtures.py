"""Synthetic reviewed table/prose chunks for reproducible live token qualification."""

from smb_requirement_agent.application.use_cases.documents import UploadDocumentInput
from smb_requirement_agent.application.use_cases.requirement_knowledge import bounded_knowledge_text
from smb_requirement_agent.domain.document.library import ReviewedPassage
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.interfaces.api.container import build_container
from tests.delimited_fixtures import reviewed_delimited_table
from tests.presentation_fixtures import PPTX_MIME, reviewed_table_presentation
from tests.spreadsheet_fixtures import XLSX_MIME, reviewed_spreadsheet_document
from tests.word_table_fixtures import DOCX_MIME, reviewed_word_table_document


def chunk_token_samples() -> tuple[tuple[str, str], ...]:
    fixtures = [
        ("docx", DOCX_MIME, reviewed_word_table_document(), 3),
        ("pptx", PPTX_MIME, reviewed_table_presentation(), 1),
        ("xlsx", XLSX_MIME, reviewed_spreadsheet_document(), 3),
        *((kind, *reviewed_delimited_table(kind), 1) for kind in ("csv", "tsv")),
        ("txt", "text/plain", ("التغطية مطلوبة. Coverage required! 🙂 " * 60).encode(), 0),
        (
            "md",
            "text/markdown",
            ("# Heading\n" + "Eligibility requires a valid address. " * 60).encode(),
            1,
        ),
    ]
    samples: list[tuple[str, str]] = []
    for kind, mime, content, included in fixtures:
        container = build_container(
            Settings(llm_provider=LLMProvider.FAKE, library_scan_mode="offline")
        )
        try:
            service, knowledge = container.document_library, container.reference_knowledge
            actor = FAKE_ACTORS[0]
            document = service.submit(
                "Coverage policy", UploadDocumentInput(f"policy.{kind}", mime, content), kind, actor
            )
            assert service.process_next()
            view = service.get(document.id, actor)
            source = view.versions[-1]
            service.review(
                document.id,
                source.id,
                view.version,
                actor,
                tuple(
                    ReviewedPassage(
                        b.id, b.text or "", i == included, "Excluded" if i != included else ""
                    )
                    for i, b in enumerate(source.blocks)
                ),
                "Synthetic fixture review",
            )
            preview = knowledge.preview_build(document.id, actor)
            assert "".join(c.original_text for c in preview.chunks) == source.blocks[included].text
            assert all(c.token_count <= 768 for c in preview.chunks)
            assert all(
                "private" not in c.search_text and "Private" not in c.context_text
                for c in preview.chunks
            )
            samples.extend(
                (f"{kind}-child-{i + 1}", c.search_text) for i, c in enumerate(preview.chunks)
            )
            samples.append((f"{kind}-context", preview.chunks[0].context_text))
        finally:
            container.close_resources()
            container.debug_trace.close()
    for name, text in (
        ("arabic", "التغطية مطلوبة قبل الطلب. " * 70),
        ("mixed", "BCRM التغطية 🙂 e\u0301 ! | " * 150),
        ("unbroken", "0123456789abcdef" * 150),
    ):
        samples.extend(
            (f"requirement-{name}-{i + 1}", part)
            for i, part in enumerate(bounded_knowledge_text(text))
        )
    return tuple(samples)


if __name__ == "__main__":
    import json
    from pathlib import Path

    values = chunk_token_samples()
    target = Path("docs/evaluation/chunk-token-fixtures.json")
    target.parent.mkdir(exist_ok=True)
    target.write_text(
        json.dumps(
            [{"case": name, "text": text} for name, text in values], indent=2, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(values)} synthetic samples to {target}")
