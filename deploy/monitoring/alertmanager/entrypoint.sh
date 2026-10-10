#!/bin/sh
# Renders Alertmanager's configuration for the chosen receiver, then starts it.
#
#   ALERTMANAGER_RECEIVER  none (default): alerts show in Alertmanager and Grafana only
#                          webhook: POST each notification to a URL
#                          slack:   post to a Slack incoming webhook
#
# The URL (ALERTMANAGER_URL) is a secret: it is written to a file only this process can
# read, on the container's tmpfs, and the configuration names the file, never the URL.
# `entrypoint.sh check` renders the configuration and validates it with amtool instead.
set -eu

receiver="${ALERTMANAGER_RECEIVER:-none}"
config="${ALERTMANAGER_CONFIG:-/tmp/alertmanager.yml}"
secret="${ALERTMANAGER_URL_FILE:-/tmp/alertmanager_url}"

if [ -n "${ALERTMANAGER_URL:-}" ]; then
  (umask 077 && printf '%s' "$ALERTMANAGER_URL" > "$secret")
fi
unset ALERTMANAGER_URL

case "$receiver" in
  none)
    target="    # Nothing is sent: firing alerts are visible in Alertmanager and Grafana."
    ;;
  webhook)
    target="    webhook_configs:
      - url_file: $secret
        send_resolved: true"
    ;;
  slack)
    target="    slack_configs:
      - api_url_file: $secret
        send_resolved: true
        title: '{{ .CommonLabels.alertname }} ({{ .Status }})'
        text: '{{ range .Alerts }}- {{ .Annotations.summary }} ({{ .Annotations.runbook_url }}) {{ end }}'"
    ;;
  *)
    echo "ALERTMANAGER_RECEIVER must be none, webhook or slack, not '$receiver'." >&2
    exit 2
    ;;
esac

if [ "$receiver" != none ] && [ ! -s "$secret" ]; then
  echo "ALERTMANAGER_RECEIVER=$receiver needs ALERTMANAGER_URL; $secret is empty." >&2
  exit 2
fi

cat > "$config" <<CONFIG
# Rendered by entrypoint.sh for ALERTMANAGER_RECEIVER=$receiver; edit the script, not this file.
route:
  receiver: operators
  group_by: [alertname, severity]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    # Informational alerts are shown, never sent.
    - receiver: silent
      matchers: ['severity="info"']

inhibit_rules:
  # A container that cannot be scraped explains its own missing or failing signals.
  - source_matchers: ['alertname="ProcessDown"']
    target_matchers: ['severity=~"warning|info"']
    equal: [instance]

receivers:
  - name: silent
  - name: operators
$target
CONFIG

if [ "${1:-}" = check ]; then
  exec amtool check-config "$config"
fi
exec alertmanager --config.file="$config" --storage.path=/alertmanager "$@"
