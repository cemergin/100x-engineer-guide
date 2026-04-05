# L2-M47: Alerting & On-Call

> **Loop 2 (Practice)** | Section 2C: Infrastructure & Operations | ⏱️ 60 min | 🟢 Core | Prerequisites: L2-M45, L2-M46
>
> **Source:** Chapters 4, 18 of the 100x Engineer Guide

## What You'll Learn

- Alert philosophy: alert on symptoms, not causes; every alert must be actionable
- Configuring SLO-based alerts for TicketPulse using metrics from L2-M45
- Multi-window, multi-burn-rate alerting to avoid flapping and false pages
- Alert routing: which problems page, which create tickets, which are dashboard-only
- Writing a runbook that someone at 3 AM can follow
- Setting up a fair, sustainable on-call rotation
- The difference between alerting and monitoring

## Why This Matters

TicketPulse is running in production with Prometheus metrics and Grafana dashboards. But dashboards require someone to be looking at them. At 3 AM on a Saturday, nobody is looking. Alerts bridge that gap: when a metric crosses a threshold that indicates user impact, the right person gets paged.

Bad alerting is worse than no alerting. If your team gets paged 5 times a night for non-issues, they stop trusting alerts, start ignoring them, and miss the real incident. Good alerting means: every page is a real problem, every page has a runbook, and the on-call engineer has enough context to act.

## Prereq Check

You need the Prometheus alerting rules from L2-M45 and the TicketPulse metrics flowing.

```bash
# Verify Prometheus is running and has alert rules
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[].name'
# Should show: HighErrorRate, HighLatency, PurchaseFailureRate, TargetDown, HighMemoryUsage
```

---

## 1. Reflect: What Should Wake You Up at 3 AM?

Before writing any alert rules, think about this question.

**Should page (wake someone up):**
- Users cannot purchase tickets (revenue impact)
- The entire site is down (complete outage)
- Data is being corrupted or lost (irreversible damage)
- Security breach detected (active threat)

**Should NOT page:**
- CPU usage is at 75% (no user impact yet)
- Disk is 80% full (not urgent, can wait until morning)
- One pod restarted (K8s self-healed, no user noticed)
- A non-critical background job failed (retry will handle it)

The principle: **alert on symptoms (user-visible impact), not causes (infrastructure metrics).** CPU at 95% is only a problem if it causes slow responses or errors. Alert on the slow responses, not the CPU.

---

## 2. Build: SLO-Based Alerts for TicketPulse

We defined SLOs in earlier modules. Now we turn them into alerts.

<details>
<summary>💡 Hint 1: Burn Rate Math</summary>
Burn rate = (actual error rate) / (SLO error budget rate). For a 99.9% SLO, the error budget is 0.1%. A 14.4x burn rate means errors are occurring at 14.4 * 0.1% = 1.44% -- you will exhaust 30 days of budget in about 2 days. Use two thresholds: 14.4x for critical (page) and 6x for warning (ticket).
</details>

<details>
<summary>💡 Hint 2: Multi-Window Structure</summary>
Each burn-rate alert uses two PromQL windows joined by <code>and</code>: a long window (1h or 6h) ensures the problem is sustained, and a short window (5m or 30m) ensures the problem is still happening right now. This prevents both false positives from brief spikes and stale alerts from resolved issues.
</details>

<details>
<summary>💡 Hint 3: Routing with PagerDuty</summary>
In Alertmanager's <code>route</code> config, match on the <code>severity</code> label: <code>critical</code> routes to a PagerDuty receiver (pages the on-call), <code>warning</code> routes to Slack (creates a ticket). Use <code>group_by: ['alertname', 'slo']</code> to avoid alert storms where one root cause triggers multiple pages.
</details>

### SLO 1: 99.9% Availability

**What it means:** Over a 30-day window, at most 0.1% of requests can be errors. That is 43.2 minutes of total error time per month.

**Naive alert (do NOT use this):**

```yaml
# BAD -- fires on any spike, extremely noisy
- alert: HighErrorRate
  expr: rate(http_requests_total{status_code=~"5.."}[1m]) > 0
  for: 0s
```

This fires on a single error. Useless.

**Better alert (what we built in L2-M45):**

```yaml
# OK -- fires if error rate exceeds 0.1% for 5 minutes
- alert: HighErrorRate
  expr: |
    (
      sum(rate(http_requests_total{status_code=~"5.."}[5m]))
      /
      sum(rate(http_requests_total[5m]))
    ) > 0.001
  for: 5m
```

This is decent but has a problem: it uses a single window (5 minutes). A brief spike can trigger it, and a slow burn can take a long time to detect.

**Best alert: multi-window, multi-burn-rate.**

### Multi-Window, Multi-Burn-Rate Alerts

The idea: alert faster for severe problems, slower for minor ones. Use two windows to catch both.

**Burn rate** = how fast you are consuming your error budget. If your 30-day error budget is 0.1%:
- Burn rate 1x = you will exhaust the budget in exactly 30 days (not urgent)
- Burn rate 14.4x = you will exhaust the budget in 2 days (urgent)
- Burn rate 36x = you will exhaust the budget in 20 hours (critical)

```yaml
# monitoring/alert-rules.yml (replace the previous HighErrorRate)

groups:
  - name: ticketpulse-slo-burn-rate
    rules:
      # =============================================
      # Availability SLO: 99.9% (error budget: 0.1%)
      # =============================================

      # Critical: 14.4x burn rate over both 1h and 5m windows
      # Will exhaust 30-day budget in 2 days
      # Page immediately
      - alert: HighErrorRate_Critical
        expr: |
          (
            sum(rate(http_requests_total{status_code=~"5.."}[1h]))
            / sum(rate(http_requests_total[1h]))
            > (14.4 * 0.001)
          )
          and
          (
            sum(rate(http_requests_total{status_code=~"5.."}[5m]))
            / sum(rate(http_requests_total[5m]))
            > (14.4 * 0.001)
          )
        for: 2m
        labels:
          severity: critical
          slo: availability
          team: ticketpulse
        annotations:
          summary: "Critical: error rate burning SLO budget at 14.4x"
          description: |
            Error rate is {{ $value | humanizePercentage }} over the last hour.
            At this rate, the 30-day error budget will be exhausted in ~2 days.
            Immediate investigation required.
          runbook_url: "https://wiki.internal/runbooks/high-error-rate"

      # Warning: 6x burn rate over both 6h and 30m windows
      # Will exhaust 30-day budget in 5 days
      # Create a ticket, do not page
      - alert: HighErrorRate_Warning
        expr: |
          (
            sum(rate(http_requests_total{status_code=~"5.."}[6h]))
            / sum(rate(http_requests_total[6h]))
            > (6 * 0.001)
          )
          and
          (
            sum(rate(http_requests_total{status_code=~"5.."}[30m]))
            / sum(rate(http_requests_total[30m]))
            > (6 * 0.001)
          )
        for: 15m
        labels:
          severity: warning
          slo: availability
          team: ticketpulse
        annotations:
          summary: "Warning: elevated error rate burning SLO budget at 6x"
          description: |
            Error rate has been elevated for the past 6 hours.
            At this rate, the 30-day error budget will be exhausted in ~5 days.
            Investigate during business hours.

      # =============================================
      # Latency SLO: 99% of requests < 1s
      # =============================================

      - alert: HighLatency_Critical
        expr: |
          (
            1 - (
              sum(rate(http_request_duration_seconds_bucket{le="1"}[1h]))
              / sum(rate(http_request_duration_seconds_count[1h]))
            )
          ) > (14.4 * 0.01)
          and
          (
            1 - (
              sum(rate(http_request_duration_seconds_bucket{le="1"}[5m]))
              / sum(rate(http_request_duration_seconds_count[5m]))
            )
          ) > (14.4 * 0.01)
        for: 2m
        labels:
          severity: critical
          slo: latency
        annotations:
          summary: "Critical: p99 latency SLO burning at 14.4x"
          description: |
            More than {{ $value | humanizePercentage }} of requests are exceeding 1s.
            Check: slow database queries, downstream service issues, resource exhaustion.
          runbook_url: "https://wiki.internal/runbooks/high-latency"

      # =============================================
      # Purchase Success SLO: 99.95%
      # =============================================

      - alert: PurchaseFailures_Critical
        expr: |
          (
            sum(rate(ticketpulse_purchase_attempts_total{outcome!="success"}[1h]))
            / sum(rate(ticketpulse_purchase_attempts_total[1h]))
            > (14.4 * 0.0005)
          )
          and
          (
            sum(rate(ticketpulse_purchase_attempts_total{outcome!="success"}[5m]))
            / sum(rate(ticketpulse_purchase_attempts_total[5m]))
            > (14.4 * 0.0005)
          )
        for: 2m
        labels:
          severity: critical
          slo: purchases
        annotations:
          summary: "Critical: purchase failure rate burning SLO budget"
          description: |
            Purchase failures are elevated. Revenue is being lost.
            Check payment service health, Stripe API status, and database connectivity.
          runbook_url: "https://wiki.internal/runbooks/purchase-failures"
```

### Why two windows?

The **long window** (1h, 6h) ensures the problem is sustained, not a brief spike. The **short window** (5m, 30m) ensures the problem is still happening right now. Together, they prevent:

- **False positives:** A 30-second error spike triggers the 5m window but not the 1h window. No alert.
- **Stale alerts:** The problem happened 4 hours ago but has stopped. The 1h window fires but the 5m window does not. No alert.

Reload Prometheus:

```bash
curl -X POST http://localhost:9090/-/reload
```

---

## 3. Alert Routing

Not every alert deserves a page. Use severity labels to route alerts to the right channel.

| Severity | Routing | Response Time | Examples |
|----------|---------|---------------|----------|
| `critical` | Page (PagerDuty/Opsgenie) | 5 minutes | Complete outage, data loss, purchase failures |
| `warning` | Ticket (Jira/Linear) | Next business day | Elevated error rate, slow latency trend |
| `info` | Dashboard only | When someone looks | High memory usage, disk filling slowly |

In a real setup, you would configure Alertmanager (Prometheus's alert router) to send critical alerts to PagerDuty and warning alerts to Slack:

```yaml
# monitoring/alertmanager.yml (reference -- not needed for local setup)

global:
  resolve_timeout: 5m

route:
  receiver: 'default'
  group_by: ['alertname', 'slo']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

  routes:
    # Critical alerts → PagerDuty
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
      repeat_interval: 1h

    # Warning alerts → Slack
    - match:
        severity: warning
      receiver: 'slack-warnings'
      repeat_interval: 12h

receivers:
  - name: 'default'
    slack_configs:
      - channel: '#ticketpulse-alerts'

  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: '<pagerduty-service-key>'
        severity: 'critical'

  - name: 'slack-warnings'
    slack_configs:
      - channel: '#ticketpulse-alerts'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ .CommonAnnotations.description }}'
```

---

## 4. Build: A Runbook for "High Error Rate"

Every alert needs a runbook. A runbook is a step-by-step guide that an on-call engineer -- who may not be familiar with this service -- can follow at 3 AM.

<details>
<summary>💡 Hint 1: First 5 Minutes</summary>
Start the runbook with scope identification: <code>sum by (service) (rate(http_requests_total{status_code=~"5.."}[5m]))</code> tells you which service is erroring. Then check for recent deployments: <code>kubectl rollout history deployment -n ticketpulse</code>. A deployment in the last 30 minutes is the likely cause.
</details>

<details>
<summary>💡 Hint 2: Copy-Pasteable Commands</summary>
Every runbook command should work as-is when pasted into a terminal at 3 AM. Include the full namespace, full label selectors, and exact flags. For example: <code>kubectl logs -n ticketpulse -l app=payment-service --tail=100 --since=10m | grep ERROR</code> -- not "check the payment service logs."
</details>

<details>
<summary>💡 Hint 3: Mitigation Before Root Cause</summary>
The runbook should prioritize stopping the bleeding. If a deployment caused it: <code>kubectl rollout undo deployment/&lt;service&gt; -n ticketpulse</code>. If an external dependency is down, check its status page and verify the circuit breaker is active. Investigate root cause AFTER the error rate is back within SLO.
</details>

Create a runbook for the HighErrorRate alert:

```markdown
# Runbook: HighErrorRate_Critical

## Alert Description
Error rate has exceeded the 99.9% availability SLO burn rate threshold.
More than 1.44% of requests are returning 5xx errors.

## Impact
Users are experiencing errors when using TicketPulse.
If the error rate affects the purchase flow, revenue is being lost.

## First Response (0-5 minutes)

### Step 1: Scope the problem
Is it one service or all services?

```promql
sum by (service) (rate(http_requests_total{status_code=~"5.."}[5m]))
```

Open Grafana → TicketPulse Overview → Error Rate panel.
If one service is red and others are green, focus on that service.

### Step 2: Check for recent deployments
```bash
kubectl rollout history deployment -n ticketpulse
# Look for deployments in the last 30 minutes
```

If a deployment happened recently, it is likely the cause. Proceed to Rollback.

### Step 3: Check dependency health
```bash
# Database
kubectl exec -it -n ticketpulse <any-pod> -- wget -qO- http://localhost:3000/health

# Kafka
kubectl get pods -n ticketpulse -l app=kafka

# Check Prometheus targets
# http://localhost:9090/targets -- any targets DOWN?
```

### Step 4: Check service logs
```bash
kubectl logs -n ticketpulse -l app=api-gateway --tail=100 --since=10m | grep ERROR
kubectl logs -n ticketpulse -l app=event-service --tail=100 --since=10m | grep ERROR
kubectl logs -n ticketpulse -l app=payment-service --tail=100 --since=10m | grep ERROR
```

Look for: connection refused, timeout, OOM, unhandled exception.

### Step 5: Check traces
Open Jaeger → search for traces with errors in the last 15 minutes.
Look at the trace waterfall to identify which service/operation is failing.

## Mitigation Actions

### If deployment-related:
```bash
kubectl rollout undo deployment/<service-name> -n ticketpulse
```
Wait 2 minutes. Verify error rate drops.

### If database-related:
- Check PostgreSQL logs: `kubectl logs -n ticketpulse -l app=postgres`
- Check connection pool: are connections exhausted?
- Check for long-running queries: `SELECT * FROM pg_stat_activity WHERE state = 'active';`

### If external dependency (Stripe, etc.):
- Check status page: https://status.stripe.com
- If Stripe is down, TicketPulse should degrade gracefully (circuit breaker)
- If circuit breaker is not working, the fix is code-level (escalate)

### If cause is unknown:
- Restart the affected service: `kubectl rollout restart deployment/<service-name> -n ticketpulse`
- If restart does not help, escalate to the service owner

## Escalation
- Primary: on-call engineer (this is you)
- Secondary: service owner (check rotation schedule)
- Manager: if not resolved in 30 minutes and revenue impact confirmed
```

### What makes a good runbook

1. **No assumptions about the reader's knowledge.** They might be a new team member on their first on-call shift.
2. **Copy-pasteable commands.** Every command should work as-is, no "replace X with Y" unless unavoidable.
3. **Decision trees, not essays.** "If A, do B. If C, do D." Not paragraphs of context.
4. **Mitigation before root cause.** Stop the bleeding first. Investigate later.
5. **Escalation path.** The on-call engineer should never feel stuck with no options.

---

## 5. On-Call Rotation

A sustainable on-call rotation keeps the team healthy and the system reliable.

### Rotation structure

```
Week 1: Alice (primary), Bob (secondary)
Week 2: Bob (primary), Charlie (secondary)
Week 3: Charlie (primary), Alice (secondary)
...
```

**Primary** handles all pages. **Secondary** is backup if primary does not acknowledge within 5 minutes.

### On-call best practices

**Target: fewer than 2 pages per 12-hour shift.** If the team is getting paged more, the alerts are too noisy or the system is too fragile. Fix the alerts or fix the system.

**Handoff process:** At rotation change, the outgoing on-call writes a brief handoff:
- What happened this week (incidents, near-misses)
- What is different from last week (new deployments, config changes)
- What to watch for (known issues, upcoming events)

**Shadow on-call:** New team members shadow for 1-2 rotations before going primary. They receive all pages but are not expected to respond alone.

**Compensation:** On-call work is real work. Compensate with extra pay, comp time, or reduced sprint commitments. A team that resents on-call will not do it well.

**Post-incident review:** After every page, evaluate: was this alert necessary? Could the system have self-healed? Should the runbook be updated? Does the alert threshold need adjustment?

### On-call tools

| Tool | Purpose |
|------|---------|
| PagerDuty / Opsgenie / Grafana OnCall | Alert routing, escalation, rotation management |
| Slack / Teams | Incident communication channel |
| StatusPage | External communication to users |
| Jira / Linear | Tracking follow-up work from incidents |
| Postmortem template | Structured incident review document |

---

## 6. Reflect

> **Write a 1-paragraph runbook for: "TicketPulse p99 latency is 5x normal."**
>
> Example: "Check the Grafana latency panel to confirm the p99 spike and identify which service is affected. Open Jaeger and search for slow traces (duration > 2s) in the last 15 minutes. Look at the trace waterfall to identify the slow span -- if it is a database query, check `pg_stat_activity` for long-running queries and `pg_stat_user_tables` for sequential scans. If it is an external API call (Stripe, etc.), check their status page and verify the circuit breaker is functioning. If it is CPU-bound, check `kubectl top pods` for resource exhaustion and scale the deployment. Mitigate by scaling up replicas (`kubectl scale deployment --replicas=5`) while investigating the root cause."

> **"Our error budget is 43.2 minutes per month. We had a 10-minute outage. Should we freeze deployments?"**
>
> You have consumed 23% of your monthly error budget. That is significant but not critical. Do not freeze deployments -- that creates a culture of fear. Instead: run a postmortem, fix the root cause, and add monitoring to catch similar issues earlier. Only freeze deployments if the budget is >50% consumed and the root cause is unknown.

> **"What is the difference between monitoring and alerting?"**
>
> Monitoring is observing: collecting metrics, building dashboards, understanding system behavior. Alerting is acting: automatically notifying humans when metrics indicate a problem. You monitor everything; you alert on the small subset that requires immediate human intervention. Too many alerts means you are not monitoring well enough to set good thresholds.

> **What did you notice?** After following the runbook step by step, how long did it take to identify the problem? What would you add to the runbook to make the next response faster?

---

## 7. Checkpoint

After this module, you should have:

- [ ] Multi-window, multi-burn-rate alert rules for availability, latency, and purchase success SLOs
- [ ] Understanding of burn rate: what it means for 14.4x vs 6x vs 1x budget consumption
- [ ] Alert routing strategy: critical (page), warning (ticket), info (dashboard)
- [ ] A runbook for the HighErrorRate alert with copy-pasteable commands
- [ ] Understanding of on-call rotation structure and best practices
- [ ] You have manually triggered an alert and observed it in Prometheus
- [ ] Alertmanager configuration reference for routing to PagerDuty/Slack
- [ ] A written runbook paragraph for the "high latency" scenario

**Next up:** L2-M48 where we intentionally break TicketPulse with chaos engineering and see if our monitoring and alerting catches the problems.

---

> **Before you continue:** If you inject a 15% error rate into the event service, how long do you predict it will take for the HighErrorRate_Critical alert to fire? Consider the `for: 2m` clause and the multi-window evaluation.

## 8. Hands-On Walkthrough: Trigger and Respond to an Alert (20 min)

Theory only takes you so far. This walkthrough makes you experience the full alert lifecycle: trigger, page, diagnose, mitigate.

### Step 1: Create a Synthetic Failure

Inject a high error rate into TicketPulse's event service:

```bash
# Option A: Kill the event-service pod (complete outage)
kubectl delete pod -n ticketpulse -l app=event-service

# Option B: Inject errors via environment variable (if your service supports it)
kubectl set env deployment/event-service -n ticketpulse ERROR_RATE=0.5
# Then roll it back: kubectl set env deployment/event-service -n ticketpulse ERROR_RATE=0

# Option C: Simulate with a Prometheus metric injection (most controlled)
# If you have a /internal/inject-errors endpoint for testing:
curl -X POST http://localhost:3000/internal/inject-errors \
  -H 'Content-Type: application/json' \
  -d '{"rate": 0.15, "durationSeconds": 300}'
```

### Step 2: Watch the Alert Fire in Prometheus

```bash
# Watch the rules evaluation every 15 seconds
watch -n 15 'curl -s http://localhost:9090/api/v1/alerts | jq ".data.alerts[] | {name: .labels.alertname, state: .state, value: .annotations.description}"'
```

Expected progression:
```
After ~30s:  PENDING (threshold crossed but for: 2m not elapsed yet)
After ~2m:   FIRING (alert is now active)
```

### Step 3: Receive the Alert (Slack Simulation)

In a real setup, PagerDuty would wake you up. For this exercise, check Alertmanager's local UI or Slack webhook:

```bash
# Alertmanager UI (if running locally)
open http://localhost:9093

# List active alerts via API
curl -s http://localhost:9093/api/v1/alerts | jq '.data[] | {name: .labels.alertname, severity: .labels.severity}'
```

### Step 4: Follow Your Runbook

Now practice being an on-call engineer. Work through the HighErrorRate runbook you wrote above:

```bash
# Step 1: Which service is erroring?
curl -s 'http://localhost:9090/api/v1/query?query=sum+by+(service)+(rate(http_requests_total{status_code=~"5.."}[5m]))' \
  | jq '.data.result[] | {service: .metric.service, rate: .value[1]}'

# Step 2: Check recent deployments
kubectl rollout history deployment -n ticketpulse

# Step 3: Check logs
kubectl logs -n ticketpulse -l app=event-service --tail=50 --since=5m | grep -E "ERROR|error|Error"

# Step 4: Check health endpoint
kubectl exec -it deploy/api-gateway -n ticketpulse -- \
  wget -qO- http://event-service:3000/health
```

### Step 5: Resolve and Verify Alert Clears

```bash
# Undo the synthetic failure
kubectl rollout restart deployment/event-service -n ticketpulse
# -- OR --
kubectl set env deployment/event-service -n ticketpulse ERROR_RATE=0

# Wait for the alert to clear (watch the burn rate drop below threshold)
watch -n 30 'curl -s http://localhost:9090/api/v1/alerts | jq ".data.alerts | length"'
# Should go to 0 after the for: 2m window resolves
```

### Step 6: Write a Mini Postmortem

Even for a synthetic incident, practice the format:

```markdown
## Incident: HighErrorRate_Critical (Synthetic)

**Duration**: 12:03 PM – 12:18 PM (15 minutes)
**Impact**: 15% of requests to event-service returned 5xx errors.
**Burn rate**: ~6x the SLO error budget

**Timeline**:
- 12:03: Error injection started (simulated)
- 12:05: Alert entered PENDING state
- 12:07: Alert FIRED, on-call engineer paged
- 12:10: Engineer began runbook. Identified event-service pod was OOM-killed.
- 12:15: Rollout restart issued
- 12:18: Error rate normalized, alert resolved

**Root cause**: Memory limit too low for current traffic; pod hit the limit and was killed.

**Action items**:
- [ ] Increase memory limit for event-service from 256Mi to 512Mi
- [ ] Add OOM kill alert (kubernetes_pod_oom_kills_total)
- [ ] Add a load test to CI that catches OOM at 2x expected traffic

**Lessons**:
- The runbook worked — reduced time to mitigation from "no idea" to 8 minutes.
- Alert firing correctly at 2m into the incident. Good sensitivity.
```

---

## 9. Extended Reflection: Alert Design Decisions (10 min)

Work through these scenarios. There is no single right answer — the goal is to reason through trade-offs.

### Scenario A: Alert Fatigue

Your team is getting paged 8 times per night, and 7 of those pages turn out to be noise (auto-resolved within 10 minutes, no user impact). The team starts ignoring alerts. What do you do?

> **Guided approach**: Do not raise the threshold blindly. First, analyze: which alerts are noisy? Are they flapping (firing and resolving repeatedly)? Increase the `for:` duration on those specific alerts. Second, check if the metric is the right signal — CPU at 95% is rarely the right thing to alert on. Switch to latency or error rate. Third, add a `group_wait` in Alertmanager to prevent alert storms where one root cause triggers 10 dependent alerts.

### Scenario B: The Slow Burn

Your error budget is draining at 2x the normal rate — not urgent enough for a page, but you will exhaust the budget in 15 days instead of 30. The on-call rotation changes in 3 days. What does the alert system do?

> **Guided approach**: This is exactly the 6x burn rate scenario (Warning severity). It should create a Jira ticket automatically via Alertmanager's webhook receiver, not page anyone. The incoming on-call engineer should see this open ticket in their handoff notes. The key: warning alerts must actually flow to a tracking system, not just Slack, or they get lost.

### Scenario C: Disagreement on Severity

Your colleague says: "Disk at 85% is critical — we should page on it." You say: "Disk at 85% is fine, we have two weeks before it's full." How do you resolve this?

> **Guided approach**: Convert the metric to time-to-impact. `node_filesystem_avail_bytes` combined with a fill-rate projection tells you "at current rate, disk will be full in N days." Page if N < 1 day. Create a ticket if N < 7 days. Dashboard-only if N > 7 days. Remove the opinion from the discussion by making it concrete.

---

> **Want the deep theory?** See Ch 18 of the 100x Engineer Guide: "Alert Design and On-Call Culture" — covers the full Google SRE burn rate methodology and alert routing patterns used at scale.

---

## Glossary

| Term | Definition |
|------|-----------|
| **SLO (Service Level Objective)** | A target for system reliability, expressed as a percentage over a time window (e.g., 99.9% availability over 30 days). |
| **Error Budget** | The allowed amount of unreliability. 99.9% SLO = 0.1% error budget = 43.2 minutes/month of allowed errors. |
| **Burn Rate** | How fast the error budget is being consumed. 1x = normal, 14.4x = will exhaust 30-day budget in 2 days. |
| **Multi-Window Alert** | An alert that requires thresholds to be breached in both a long window (sustained) and short window (current). Reduces false positives and stale alerts. |
| **Runbook** | A step-by-step guide for diagnosing and mitigating a specific alert. Written for someone who may be unfamiliar with the system. |
| **On-Call** | A rotation where team members are responsible for responding to production alerts outside business hours. |
| **Page** | An alert notification that interrupts the on-call engineer (phone call, SMS, push notification). Reserved for critical issues. |
| **Alertmanager** | The Prometheus component that handles alert routing, grouping, silencing, and notification to external systems. |
| **Symptom-Based Alerting** | Alerting on user-visible impact (errors, latency) rather than causes (CPU, memory). |
| **Flapping** | An alert that rapidly toggles between firing and resolved, creating noise. Prevented by `for` durations and multi-window rules. |
| **Escalation** | The process of notifying additional people when the primary on-call does not acknowledge or cannot resolve an alert. |
| **Postmortem** | A blameless review after an incident, documenting what happened, why, and what will be done to prevent recurrence. |

---

## What's Next

In **Chaos Engineering** (L2-M48), you'll deliberately break TicketPulse in controlled ways to discover weaknesses before your users do.
