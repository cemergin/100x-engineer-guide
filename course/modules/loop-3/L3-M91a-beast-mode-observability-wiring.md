# L3-M91a: Beast Mode — Observability & Dashboard Wiring

> **Loop 3 (Mastery)** | Section 3F: Operational Readiness | ⏱️ 75 min | 🟢 Core | Prerequisites: L3-M91 (Access & System Mapping), L2-M45 (Monitoring), L2-M46 (Distributed Tracing)
>
> **Source:** Chapter 36 of the 100x Engineer Guide

## What You'll Learn

- Building a personal hotlinks dashboard for rapid incident triage
- Learning what "normal" looks like by studying baseline metrics
- Understanding alerting topology — who gets paged and why
- The "metrics don't lie" principle — trusting observable truth over documentation

## Why This Matters

In L3-M91 you verified access and mapped the architecture. You can reach every layer of the stack. You can draw the system from memory. But can you look at a Grafana dashboard right now and tell whether TicketPulse is healthy? Can you distinguish a normal traffic dip (3 AM lull) from an early sign of a database connection leak?

The engineer who knows where to look beats the engineer who knows the code. Your eyes and ears need to be wired before an incident, not during one. An engineer who opens five browser tabs, types three half-remembered Grafana URLs, and spends eight minutes finding the right dashboard while the CEO is asking "what is happening?" is not ready. An engineer who opens a single bookmarked page, sees every golden signal at a glance, and says "p99 latency spiked at 14:32, correlating with a deployment at 14:30 — rolling back now" is ready.

You have built the monitoring stack in L2-M45 and L2-M46. You wired up Prometheus, Grafana, and OpenTelemetry. Now you learn to USE it like someone who has been on the TicketPulse team for months — someone who can feel that something is wrong before the alerts even fire.

> 💡 **Insight**: "The best on-call engineers are not the ones who respond fastest to pages. They are the ones who notice problems before the page fires — because they have internalized what 'normal' looks like, and anything that deviates from normal triggers their attention immediately."

---

## The Scenario

**You are now two days into your TicketPulse rotation.** You verified access and mapped the architecture in L3-M91. Today, your tech lead says:

> "Great, you can reach everything. But I need you on-call next week. Before that happens, I need to know that you can actually read the dashboards, that you have your hotlinks ready, and that you understand our alerting rules. Spend the next hour wiring yourself in."

---

## Phase 1: Learn What Normal Looks Like (~20 min)

### 📊 Observe: Baseline Capture

Before you can detect anomalies, you must know what healthy looks like. A p99 latency of 800ms means nothing without context — is that good? Bad? Normal for Tuesday at 2 PM?

**Step 1 — Open the Grafana dashboards.** Navigate to your TicketPulse Grafana instance from L2-M45.

```bash
# Open Grafana (from your docker-compose or k8s setup)
open http://localhost:3000

# If you need to confirm Prometheus targets are healthy first:
open http://localhost:9090/targets
```

**Step 2 — Study the golden signals during a calm period.** Spend 15 minutes observing. Do not click around frantically — sit and watch. Set the time range to the last 6 hours. Look at each golden signal.

Use these Prometheus/Grafana queries to pull each signal:

```promql
# REQUEST RATE — total HTTP requests per second
rate(http_requests_total{job="ticketpulse-api"}[5m])

# ERROR RATE — percentage of 5xx responses
sum(rate(http_requests_total{job="ticketpulse-api", status=~"5.."}[5m]))
/
sum(rate(http_requests_total{job="ticketpulse-api"}[5m]))

# LATENCY (p99) — 99th percentile response time
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket{job="ticketpulse-api"}[5m])) by (le)
)

# SATURATION — CPU usage per service
rate(container_cpu_usage_seconds_total{namespace="ticketpulse"}[5m])

# SATURATION — Memory usage per service
container_memory_working_set_bytes{namespace="ticketpulse"}
```

**Step 3 — Fill out the Baseline Capture Template.** Record what you observe. These numbers become your personal reference.

```
BASELINE CAPTURE TEMPLATE
═══════════════════════════════════════════════════════════════════════
Signal              │ Current Value │ 6h Range     │ Notes
════════════════════╪═══════════════╪══════════════╪══════════════════
Request rate (rps)  │               │              │ e.g., "peaks at
                    │               │              │  lunch, dips 2-5AM"
Error rate (%)      │               │              │ e.g., "steady <0.1%"
p50 latency (ms)   │               │              │
p99 latency (ms)   │               │              │ e.g., "spikes during
                    │               │              │  batch jobs at :00"
CPU utilization (%) │               │              │ per service
Memory usage (MB)   │               │              │ per service
DB connections      │               │              │ active vs pool max
Kafka consumer lag  │               │              │ per consumer group
═══════════════════════════════════════════════════════════════════════
Daily traffic shape:
  - Peak hours:
  - Quiet hours:
  - Any recurring patterns (cron jobs, batch processing):
═══════════════════════════════════════════════════════════════════════
```

**Step 4 — Identify one thing that surprised you.** Maybe the error rate is not zero (it never is). Maybe p99 is higher than you expected. Maybe there is a latency spike every hour on the hour that nobody has mentioned. Write it down.

### 🤔 Reflect

> Why is knowing "normal" so powerful? Think about it this way: a doctor does not diagnose illness by looking at a single blood test result — they compare it to baseline ranges. The same applies to systems. Without baselines, every metric is ambiguous. With baselines, deviations are obvious. What was the most surprising baseline you captured?

---

## Phase 2: Build Your Beast Mode Hotlinks Page (~30 min)

### 🛠️ Build: Your One-Page Incident Reference

When you get paged at 2 AM, you will not remember URLs. You will not remember the exact Loki query syntax for filtering order-service errors. You will not remember which Grafana dashboard has the database connection pool panel. You need a single page that gives you everything, organized for speed.

**Step 1 — Create the hotlinks file.**

```bash
# In the TicketPulse repo
touch docs/beast-mode-hotlinks.md
```

**Step 2 — Fill it out using this template.** Copy this structure and replace every URL and query with your actual values from the TicketPulse stack.

```markdown
# Beast Mode Hotlinks — TicketPulse

> Last updated: [DATE]
> On-call rotation: [LINK TO SCHEDULE]

## Primary Dashboards

| Dashboard | URL | What to Look For |
|-----------|-----|------------------|
| System Overview | http://localhost:3000/d/[DASHBOARD_ID] | All golden signals at a glance. Start here. |
| Order Service Detail | http://localhost:3000/d/[DASHBOARD_ID] | Purchase flow latency, error rate by endpoint |
| Database Metrics | http://localhost:3000/d/[DASHBOARD_ID] | Connection pool saturation, query duration |
| Kafka Overview | http://localhost:3000/d/[DASHBOARD_ID] | Consumer lag per group, broker health |

## Error Tracking

| System | URL / Command | Notes |
|--------|---------------|-------|
| Application errors | `grep "level=error" \| json` in Loki | Filter by service label |
| Unhandled exceptions | Sentry/equivalent dashboard URL | Check for new error groups |
| Failed HTTP requests | Grafana Explore: `{job="ticketpulse-api"} \|= "status=5"` | |

## Log Queries (Copy-Paste Ready)

```
# Order service errors in the last hour
{app="order-service"} |= "error" | json | line_format "{{.timestamp}} {{.msg}}"

# Payment failures
{app="payment-service"} |= "payment_failed" | json

# Slow database queries (>500ms)
{app="order-service"} |= "slow_query" | json | duration > 500ms

# Kafka consumer errors
{app=~".*-consumer"} |= "error" | json
```

## Deployment History

| Tool | URL / Command | Notes |
|------|---------------|-------|
| Recent deploys | `gh run list --limit 10` | Check if issue started after deploy |
| Current image tags | `kubectl get pods -o jsonpath='{.items[*].spec.containers[*].image}'` | Verify expected version |
| Rollback command | `kubectl rollout undo deployment/order-service` | Nuclear option |

## Infrastructure

| Component | URL / Command | What to Look For |
|-----------|---------------|------------------|
| Prometheus targets | http://localhost:9090/targets | Any targets DOWN? |
| Alertmanager | http://localhost:9093 | Active alerts, silences |
| Kubernetes pods | `kubectl get pods -n ticketpulse` | CrashLoopBackOff, OOMKilled |
| Node resources | `kubectl top nodes` | CPU/memory pressure |
| Pod resources | `kubectl top pods -n ticketpulse` | Which pod is eating resources |

## Database

| Check | Command | Threshold |
|-------|---------|-----------|
| Active connections | `SELECT count(*) FROM pg_stat_activity;` | Warn >80% of pool |
| Long-running queries | `SELECT * FROM pg_stat_activity WHERE state='active' AND query_start < now() - interval '30s';` | Any row = investigate |
| Replication lag | `SELECT extract(epoch from replay_lag) FROM pg_stat_replication;` | Warn >5s |

## Kafka

| Check | Command / URL | Threshold |
|-------|---------------|-----------|
| Consumer lag | Kafka UI or `kafka-consumer-groups.sh --describe` | Lag >10k = investigate |
| Under-replicated partitions | Prometheus: `kafka_server_replicamanager_underreplicatedpartitions` | Any >0 = alert |

## Escalation Contacts

| Role | Contact | When to Escalate |
|------|---------|-----------------|
| On-call secondary | [NAME / SLACK HANDLE] | After 15 min with no progress |
| Database owner | [NAME / SLACK HANDLE] | DB connection issues, replication |
| Platform team | #platform-oncall | Kubernetes / infrastructure issues |
| Incident commander | [NAME / SLACK HANDLE] | Customer-facing outage >5 min |
```

**Step 3 — Verify every link works.** Open each URL. Run each command. A hotlinks page with dead links is worse than no page at all — it wastes time and erodes trust during an incident.

```bash
# Quick smoke test — verify Grafana dashboards exist
curl -s http://localhost:3000/api/search | jq '.[].title'

# Verify Prometheus is reachable
curl -s http://localhost:9090/-/healthy

# Verify Alertmanager is reachable
curl -s http://localhost:9093/-/healthy
```

**Step 4 — Bookmark the hotlinks page.** Add it to your browser bookmark bar. Pin it. Make it the page that opens when you get an alert notification. The fewer clicks between "I got paged" and "I see the dashboards," the faster you respond.

### 🤔 Reflect

> How long did it take you to assemble every URL and query? Imagine doing that for the first time during an incident, at 2 AM, while half-asleep. That is why you build this page now. What sections would you add that are specific to your team or organization?

---

## Phase 3: Alert Archaeology (~25 min)

### 🔍 Explore: Understand Your Alerting Rules

You set up alerting in L2-M47. But do you actually understand every alert that exists? Could you explain each one to a new team member? Alert archaeology means digging into the rules, understanding their intent, and finding the gaps and noise.

**Step 1 — List every alerting rule.** Pull the rules from Prometheus.

```bash
# If using Prometheus operator with PrometheusRule CRDs
kubectl get prometheusrule -n monitoring -o yaml

# Or query Prometheus directly for active rules
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[] | {name: .name, query: .query, duration: .duration, labels: .labels}'

# Or find the rule files from L2-M47
find . -name "*rules*" -o -name "*alerts*" | grep -E "\.(yml|yaml)$"
cat monitoring/prometheus/alert-rules.yml
```

**Step 2 — Audit each alert.** For every alerting rule, fill out this table.

```
ALERT AUDIT TABLE
══════════════════════════════════════════════════════════════════════════════════
Alert Name            │ Trigger Condition           │ Threshold    │ For Duration
══════════════════════╪═════════════════════════════╪══════════════╪═════════════
HighErrorRate         │ error ratio > X%            │              │
HighLatencyP99        │ p99 > Xms                   │              │
PodCrashLooping       │ restart count > X in Y min  │              │
KafkaConsumerLag      │ lag > X messages            │              │
DatabaseConnPoolHigh  │ active conns > X% of max    │              │
DiskSpaceLow          │ available < X%              │              │
[add your alerts]     │                             │              │
══════════════════════╧═════════════════════════════╧══════════════╧═════════════

══════════════════════════════════════════════════════════════════════════════════
Alert Name            │ Notification Target │ Severity  │ Recommended Response
══════════════════════╪═════════════════════╪═══════════╪════════════════════════
HighErrorRate         │ #alerts-critical    │ critical  │ Check deploy history,
                      │                     │           │ then order-svc logs
HighLatencyP99        │ #alerts-warning     │ warning   │ Check DB connections,
                      │                     │           │ then Kafka lag
PodCrashLooping       │ #alerts-critical    │ critical  │ kubectl describe pod,
                      │                     │           │ check OOM / logs
KafkaConsumerLag      │ #alerts-warning     │ warning   │ Check consumer health,
                      │                     │           │ partition count
DatabaseConnPoolHigh  │ #alerts-warning     │ warning   │ Check for connection
                      │                     │           │ leaks, long queries
DiskSpaceLow          │ #alerts-warning     │ warning   │ Check log volume,
                      │                     │           │ clean or expand disk
[add your alerts]     │                     │           │
══════════════════════╧═════════════════════╧═══════════╧════════════════════════
```

**Step 3 — Find the noise.** Look for alerts that are too noisy — they fire too often and create alert fatigue. Alert fatigue is dangerous because it trains engineers to ignore pages.

Common noise patterns:
- Thresholds set too tight (fires on normal traffic spikes)
- Missing `for` duration (fires on momentary blips instead of sustained issues)
- Alerting on symptoms instead of user impact (high CPU is not always a problem)

```promql
# Check alert history — how often did each alert fire in the past week?
# In Prometheus, query the ALERTS metric:
count_over_time(ALERTS{alertstate="firing"}[7d])

# Or check Alertmanager API for recent notifications
curl -s http://localhost:9093/api/v2/alerts | jq '[.[] | .labels.alertname] | group_by(.) | map({alert: .[0], count: length}) | sort_by(.count) | reverse'
```

Identify at least one alert that fires too often. Document it:

```
NOISY ALERT ANALYSIS
═══════════════════════════════════════════════════════════
Alert:
How often it fired (last 7 days):
Why it is noisy:
Proposed fix:
  - [ ] Adjust threshold from ___ to ___
  - [ ] Add/increase `for` duration to ___
  - [ ] Change to a better metric (e.g., ___)
  - [ ] Downgrade severity from ___ to ___
═══════════════════════════════════════════════════════════
```

**Step 4 — Find the gap.** Look for failure modes that have NO alert. These are the silent killers — things that break without anyone getting notified.

Think about:
- What if the payment provider starts returning errors but the overall error rate stays below the threshold?
- What if Kafka consumer lag grows slowly over hours?
- What if a background job stops running entirely (absence of activity is hard to detect)?
- What if certificate expiry is approaching?
- What if disk usage grows linearly and will hit 100% in three days?

Identify at least one missing alert. Design it:

```
MISSING ALERT DESIGN
═══════════════════════════════════════════════════════════
Failure mode:
Why no alert exists today:
Proposed alert:
  name:
  query: |
    [PromQL query here]
  threshold:
  for:
  severity:
  notification target:
  runbook note:
═══════════════════════════════════════════════════════════
```

**Step 5 — Implement your fixes.** Update the alerting rules file from L2-M47 with your noise fix and your new alert.

```bash
# Edit the alerting rules
$EDITOR monitoring/prometheus/alert-rules.yml

# Validate the rules with promtool
promtool check rules monitoring/prometheus/alert-rules.yml

# Reload Prometheus to pick up changes
curl -X POST http://localhost:9090/-/reload
```

### 🤔 Reflect

> What did the alert audit reveal about the team's priorities? Are the alerts focused on user-facing impact or internal system metrics? Did you find that the alerting rules matched the "Top 3 Failure Scenarios" you identified in L3-M91, or were there mismatches?

---

## Wrap-Up: The "Metrics Don't Lie" Principle

You have now completed the second stage of Beast Mode preparation:

1. **Baselines captured** — you know what healthy looks like, measured in numbers, not feelings
2. **Hotlinks wired** — you have a single page that gets you from "paged" to "investigating" in under 30 seconds
3. **Alerts understood** — you know what fires, why, and what is missing

The thread running through all three phases is a single principle: **metrics don't lie.**

Documentation says "latency is under 100ms." The dashboard shows p99 at 340ms. Which do you trust? The dashboard. Always the dashboard.

Code comments say "this endpoint handles 1000 rps." Prometheus shows it has never exceeded 200 rps. Which do you trust? Prometheus.

The architecture diagram shows three replicas of the order service. `kubectl get pods` shows one, and it is in CrashLoopBackOff. Which do you trust? kubectl.

Observable truth — metrics, logs, traces, and the actual state of running infrastructure — is the only reliable source of truth. Documentation decays. Code comments lie. Diagrams become outdated the moment someone merges a PR without updating them. But Prometheus scrapes every 15 seconds. Grafana renders what is actually happening. Traces show the actual path a request took, not the path someone assumed it would take.

This does not mean documentation is useless. It means documentation is a starting point, and observable truth is the final word.

```
SELF-ASSESSMENT
═══════════════════════════════════════════════════
Area                                │ Confidence (1-5)
════════════════════════════════════╪════════════════
I can spot an anomaly on dashboards │
I know TicketPulse's baseline metrics│
My hotlinks page is complete & tested│
I can explain every alert rule      │
I found and fixed a noisy alert     │
I found and filled an alerting gap  │
════════════════════════════════════╧════════════════
```

### 🤔 Final Reflection

> During this module, where did observable truth differ from what you expected based on documentation or code? What assumptions did the metrics correct? If you were building a brand-new system tomorrow, at what point in development would you start capturing baselines — and would that be earlier than you would have said before this exercise?

---

## Further Reading

- Chapter 36: "Beast Mode" — the full philosophy behind operational readiness
- L3-M91: Beast Mode — Access & System Mapping — the access and architecture work you built on
- L2-M45: Monitoring with Prometheus & Grafana — where you built the dashboards you are now reading
- L2-M46: Distributed Tracing with OpenTelemetry — the traces that validate your mental model
- L2-M47: Alerting & On-Call — the alerting rules you audited in Phase 3
- L3-M73: Incident Response Simulation — putting your wired-in observability to the test
