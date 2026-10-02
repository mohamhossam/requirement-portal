"""Safety guards keep destructive restore preparation away from application data."""

import pytest

from tests.release_recovery import RecoveryManifest, require_test_database, verify


@pytest.mark.parametrize(
    "name", ["smb_requirements", "postgres", "application_test", "codex_qualification_test_"]
)
def test_recovery_rejects_ordinary_and_ambiguous_database_names(name: str) -> None:
    with pytest.raises(ValueError, match="disposable database"):
        require_test_database(f"postgresql://127.0.0.1/{name}")


def test_recovery_accepts_only_explicit_qualification_database() -> None:
    name = "codex_qualification_test_rehearsal"
    assert require_test_database(f"postgresql://127.0.0.1/{name}") == name


def test_restore_cannot_be_verified_against_its_source_without_restoring() -> None:
    name = "codex_qualification_test_source"
    manifest = RecoveryManifest(name, "requirement", "attachment", "checksum", {})
    with pytest.raises(ValueError, match="different database"):
        verify(f"postgresql://127.0.0.1/{name}", manifest)
