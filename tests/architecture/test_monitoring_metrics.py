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
from smb_kernel.observability import metrics

ROOT = Path(__file__).resolve().parents[2]
MONITORING = ROOT / "deploy" / "monitoring"
# The instruments are platform-kernel's (ADR-0100); this app's dashboard and alerts use them.
METRICS_MODULE = Path(metrics.__file__)
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
    used = {
        _base(name)
        for expression in expressions
        for name in _metric_names(expression)
        if name.startswith("smb_")
    }

    assert used, "No metric names found; the monitoring files moved or changed shape."
    assert used <= exported, f"Not exported by metrics.py: {sorted(used - exported)}"


# Series from the overlay's other exporters (deploy/compose.monitoring.yaml) that the alerts
# and dashboard read. Adding one here is a review decision: it must exist in the pinned image.
EXPORTER_METRICS = frozenset(
    {
        "up",  # Prometheus itself, per scrape target
        "process_resident_memory_bytes",  # the process collector in every exporter
        "pg_up",
        "pg_stat_database_numbackends",
        "pg_settings_max_connections",
        "pg_database_size_bytes",
        "node_filesystem_avail_bytes",
        "node_filesystem_size_bytes",
    }
)
_PROMQL_WORDS = frozenset(
    {"by", "without", "on", "ignoring", "and", "or", "unless", "bool", "offset"}
)
ALERTS_RUNBOOK = ROOT / "docs" / "operations" / "alerts.md"
RUNBOOK_URL = (
    "https://github.com/mohamhossam/requirement-portal/blob/main/docs/operations/alerts.md#"
)


def _metric_names(expression: str) -> set[str]:
    """The series a PromQL expression reads: identifiers that are not functions or keywords."""
    stripped = re.sub(r'"[^"]*"', '""', expression)
    stripped = re.sub(r"\{[^}]*\}", "", stripped)  # label matchers
    stripped = re.sub(r"\[[^\]]*\]", "", stripped)  # ranges
    stripped = re.sub(
        r"\b(by|without|on|ignoring|group_left|group_right)\s*\([^)]*\)", "", stripped
    )
    names = set()
    for match in re.finditer(r"(?<![\w.$])[a-zA-Z_:][a-zA-Z0-9_:]*", stripped):
        if stripped[match.end() :].lstrip().startswith("("):
            continue  # a function or an aggregation
        if match.group(0) not in _PROMQL_WORDS:
            names.add(match.group(0))
    return names


def _rules() -> list[dict[str, object]]:
    rules = yaml.safe_load(ALERTS.read_text(encoding="utf-8"))
    return [rule for group in rules["groups"] for rule in group["rules"]]


def test_the_parser_finds_series_and_skips_functions_labels_and_numbers() -> None:
    expression = (
        'max by (job) (rate(a_total{status=~"5.."}[5m])) / ignoring(state) b'
        " > 2e9 or c offset 1d unless histogram_quantile(0.95, d_bucket)"
    )

    assert _metric_names(expression) == {"a_total", "b", "c", "d_bucket"}


def test_every_series_is_an_instrument_or_an_allowed_exporter_metric() -> None:
    allowed = _exported() | EXPORTER_METRICS
    expressions = _dashboard_expressions() + _alert_expressions()
    used = {_base(name) for expression in expressions for name in _metric_names(expression)}

    assert used <= allowed, f"Neither an instrument nor allow-listed: {sorted(used - allowed)}"


def test_every_alert_has_a_severity_and_a_runbook_that_exists() -> None:
    runbook = ALERTS_RUNBOOK.read_text(encoding="utf-8")
    for rule in _rules():
        name = str(rule["alert"])
        labels = rule["labels"]
        annotations = rule["annotations"]
        assert isinstance(labels, dict) and isinstance(annotations, dict)
        assert labels["severity"] in {"critical", "warning", "info"}, name
        assert annotations["runbook_url"] == RUNBOOK_URL + name.lower(), name
        assert f"\n### {name}\n" in runbook, f"{name} has no runbook section"


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


def test_a_read_only_grafana_never_updates_its_plugins_online() -> None:
    compose = yaml.safe_load(
        (MONITORING.parent / "compose.monitoring.yaml").read_text(encoding="utf-8")
    )
    grafana = compose["services"]["grafana"]

    assert grafana["read_only"] is True
    # The preinstaller stops a bundled plugin before replacing it, so on a read-only
    # root an update online leaves the Prometheus data source unavailable.
    assert grafana["environment"]["GF_PLUGINS_PREINSTALL_DISABLED"] == "true"
