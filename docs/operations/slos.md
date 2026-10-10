# Service level objectives

**Status:** proposed 2026-10-10 with production hardening PR 9 (`docs/slices/production-hardening.md`).
They are marked for the repository owner to confirm, like the RPO and RTO in `backup-restore.md`.
Until then they are targets, not commitments.

An objective is met over its window when the indicator, measured from the metrics in
`deployment.md` ("Metrics"), stays at or above its target. The error budget is the rest: when it
is spent, reliability work comes before new features. Each objective names the alerts in
`alerts.md` that warn before the budget is gone.

| Objective | Indicator | Target | Window | Alerts |
|---|---|---|---|---|
| **The API answers** | Requests answered without a 5xx, excluding health probes | 99.5% (about 3.6 hours of full outage) | 30 days | ProcessDown, ReadinessFailing, HttpServerErrors |
| **The API answers quickly** | Requests answered within 2.5 seconds, excluding health probes | 95% | 30 days | HttpLatencyP95 (earlier, at 2 s), DbPoolSaturation |
| **AI work succeeds** | Job attempts that end in success, of those that end (cancelled and retrying attempts are excluded) | 95% | 7 days | AiJobsFailing, AiJobsExhausted, ProviderErrors |
| **AI work starts** | Minutes in which no claimable job has waited over 30 minutes | 99% | 7 days | OldestQueuedJobAge, QueueBacklog |
| **Data survives** | RPO 24 hours, RTO 1 hour (`backup-restore.md`) | — | per incident | DiskLow, DatabaseSizeGrowth |

**What is not counted**
- Requests refused as intended: 429 for rate limits and the spend budget, 4xx for invalid input.
  The spend budget pausing AI work is a decision, not an outage. It has its own alert,
  ProviderSpendBlocked.
- Provider outages that jobs ride out by retrying. These count only when a job finally fails.

## Indicators in PromQL

Replace `30d` or `7d` with the window. Run each query in Prometheus or Grafana.

```promql
# The API answers: share of requests without a 5xx.
sum(increase(smb_http_requests_total{route!~"/health|/ready", status!~"5.."}[30d]))
  / sum(increase(smb_http_requests_total{route!~"/health|/ready"}[30d]))

# The API answers quickly: share of requests within 2.5 seconds.
sum(increase(smb_http_request_duration_seconds_bucket{route!~"/health|/ready", le="2.5"}[30d]))
  / sum(increase(smb_http_request_duration_seconds_count{route!~"/health|/ready"}[30d]))

# AI work succeeds: share of ended attempts that succeeded.
sum(increase(smb_ai_jobs_total{status="succeeded"}[7d]))
  / sum(increase(smb_ai_jobs_total{status=~"succeeded|failed|error|attempts_exhausted"}[7d]))

# AI work starts: share of minutes in which no claimable job waited over 30 minutes.
avg_over_time((max(smb_ai_job_oldest_queued_age_seconds) <= bool 1800)[7d:1m])
```

## Reviewing them

- Look at the indicators once a month, and after any incident that spent budget.
- Change an objective here, together with the alert thresholds in
  `deploy/monitoring/prometheus/alerts.yml` and their tests in `alerts.test.yml`.
