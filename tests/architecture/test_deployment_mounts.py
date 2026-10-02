"""The reference deployment mounts the files its settings name by path.

The backend image holds no configuration files and runs on a read-only root
filesystem, so LLM_CONFIG_PATH can only point at a mount. Every backend process
shares the template, and a default host directory must exist in the repository:
the mounts refuse to create a missing one, so a fresh checkout (and CI) would
otherwise fail to start.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
MANIFEST = yaml.safe_load((DEPLOY / "compose.production.yaml").read_text(encoding="utf-8"))
BACKEND_SERVICES = ("api", "worker", "migrate", "maintenance", "retention")
TARGETS = {"/app/config"}


def _default_source(source: str) -> str:
    """`${VAR:-default}` -> `default`."""
    return source.split(":-", 1)[1].rstrip("}") if source.startswith("${") else source


def test_backend_template_mounts_model_files_read_only() -> None:
    mounts = {volume["target"]: volume for volume in MANIFEST["x-backend"]["volumes"]}

    assert set(mounts) == TARGETS
    for mount in mounts.values():
        assert mount["type"] == "bind"
        assert mount["read_only"] is True
        assert mount["bind"]["create_host_path"] is False
        assert (DEPLOY / _default_source(mount["source"])).is_dir(), mount["source"]


def test_every_backend_service_uses_the_template_mounts() -> None:
    template = MANIFEST["x-backend"]["volumes"]

    for name in BACKEND_SERVICES:
        assert MANIFEST["services"][name]["volumes"] == template, name
