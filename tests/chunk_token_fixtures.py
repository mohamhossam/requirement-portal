"""Synthetic requirement-knowledge chunks for reproducible live token qualification.

`docs/evaluation/chunk-token-fixtures.json` also holds reviewed library chunks
(docx/pptx/xlsx/csv/tsv/txt/md). Those are cut by the reference library, which
the knowledge service owns (ADR-0099), and are regenerated there. This module
owns only the `requirement-*` samples: requirement work's own bounded chunks.
"""

from smb_requirement_agent.application.use_cases.requirement_knowledge import bounded_knowledge_text

FIXTURE_PATH = "docs/evaluation/chunk-token-fixtures.json"
REQUIREMENT_PREFIX = "requirement-"


def chunk_token_samples() -> tuple[tuple[str, str], ...]:
    samples: list[tuple[str, str]] = []
    for name, text in (
        ("arabic", "التغطية مطلوبة قبل الطلب. " * 70),
        ("mixed", "BCRM التغطية 🙂 é ! | " * 150),
        ("unbroken", "0123456789abcdef" * 150),
    ):
        samples.extend(
            (f"{REQUIREMENT_PREFIX}{name}-{i + 1}", part)
            for i, part in enumerate(bounded_knowledge_text(text))
        )
    return tuple(samples)


if __name__ == "__main__":
    import json
    from pathlib import Path

    values = chunk_token_samples()
    target = Path(FIXTURE_PATH)
    target.parent.mkdir(exist_ok=True)
    # Keep the library's samples as the knowledge service last wrote them.
    kept = (
        [
            item
            for item in json.loads(target.read_text(encoding="utf-8"))
            if not item["case"].startswith(REQUIREMENT_PREFIX)
        ]
        if target.exists()
        else []
    )
    target.write_text(
        json.dumps(
            [*kept, *({"case": name, "text": text} for name, text in values)],
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(values)} synthetic requirement samples to {target}")
