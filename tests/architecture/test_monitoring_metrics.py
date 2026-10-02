"""The monitoring add-on only queries metrics the application exports.

The Grafana dashboard and Prometheus alert rules in deploy/monitoring name
metrics by string. A renamed or removed metric would leave a panel reading
"No data" and an alert that can never fire, with nothing failing. This test
ties every name they use to an instrument declared in the metrics module.
"""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MONITORING = ROOT / "deploy" / "monitoring"
METRICS_MODULE = (
    ROOT / "src" / "smb_requirement_agent" / "infrastructure" / "observability" / "metrics.py"
)
METRIC_NAME = re.compile(r"\bsmb_[a-z0-9_]+")
# Series Prometheus derives from a histogram's single declared name.
DERIVED_SUFFIXES = ("_bucket", "_count", "_sum")
DASHBOARD = MONITORING / "grafana" / "dashboards" / "requirement-ai.json"
ALERTS = MONITORING / "prometheus" / "alerts.yml"


def _exported() -> set[str]:
    source = METRICS_MODULE.read_text(encoding="utf-8")
    return set(re.findall(r'"(smb_[a-z0-9_]+)"', source))


def _base(name: str) -> str:
    for suffix in DERIVED_SUFFIXES:
        if name.endswith(suffix):
            return name.removesuffix(suffix)
    return name


def _dashboard_expressions() -> list[str]:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    return [target["expr"] for panel in dashboard["panels"] for target in panel.get("targets", [])]


def _alert_expressions() -> list[str]:
    rules = yaml.safe_load(ALERTS.read_text(encoding="utf-8"))
    return [rule["expr"] for group in rules["groups"] for rule in group["rules"]]


def test_the_metrics_module_declares_instruments() -> None:
    assert len(_exported()) >= 7


def test_dashboard_and_alerts_use_only_exported_metrics() -> None:
    exported = _exported()
    expressions = _dashboard_expressions() + _alert_expressions()
    used = {_base(name) for expression in expressions for name in METRIC_NAME.findall(expression)}

    assert used, "No metric names found; the monitoring files moved or changed shape."
    assert used <= exported, f"Not exported by metrics.py: {sorted(used - exported)}"


def test_every_dashboard_panel_uses_the_provisioned_datasource() -> None:
    datasources = yaml.safe_load(
        (MONITORING / "grafana" / "provisioning" / "datasources" / "prometheus.yaml").read_text(
            encoding="utf-8"
        )
    )
    uid = datasources["datasources"][0]["uid"]
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    queried = [panel for panel in dashboard["panels"] if panel.get("targets")]

    assert queried
    assert all(panel["datasource"]["uid"] == uid for panel in queried)
