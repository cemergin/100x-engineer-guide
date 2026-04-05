# L3-M78: DORA Metrics & Team Performance

> **Loop 3 (Mastery)** | Section 3C: Operations & Leadership | ⏱️ 60 min | 🟢 Core | Prerequisites: L2-M43 (CI/CD), L3-M73 (Incident Response)
>
> **Source:** Chapter 9 of the 100x Engineer Guide

## What You'll Learn

- The 4 DORA metrics and how to measure each one for TicketPulse
- DORA benchmarks: Elite, High, Medium, Low — and where TicketPulse falls
- How to build a DORA measurement dashboard from git history and CI data
- The SPACE framework as a more holistic view of engineering effectiveness
- Why Goodhart's Law makes metric-driven management dangerous
- Practical exercises for improving each DORA metric
- What to change to move TicketPulse from "High" to "Elite"

## Why This Matters

"How is the engineering team performing?" This question comes from every CEO, VP of Engineering, and board member. Without metrics, the answer is subjective: "We feel productive" or "Things are going well." With the wrong metrics (lines of code, tickets closed, hours worked), the answer is misleading.

The DORA research program (DevOps Research and Assessment), led by Dr. Nicole Forsgren, Jez Humble, and Gene Kim, studied thousands of engineering organizations over 7 years and identified 4 metrics that predict both software delivery performance AND organizational performance. These are not vanity metrics. The Accelerate book proved statistically that high DORA scores correlate with business outcomes: profitability, market share, and productivity.

> 💡 **Chapter 9 of the 100x Engineer Guide** covers engineering leadership holistically — hiring, culture, technical debt management, and measurement. This module focuses on the measurement layer and gives you the practical skills to instrument, track, and act on DORA metrics without falling into the traps that destroy their value.

---

## The 4 DORA Metrics

### Metric 1: Deployment Frequency

**Definition:** How often does the team deploy to production?

**Why it matters:** Frequent deploys mean smaller changes, which means lower risk per deploy, faster feedback, and easier rollback. Teams that deploy weekly ship 4x the features of teams that deploy monthly, because the batch size is smaller and the feedback loop is tighter.

```
MEASURING DEPLOYMENT FREQUENCY FOR TICKETPULSE
───────────────────────────────────────────────

Source: git log + CI/CD pipeline

# Count production deployments in the last 30 days
git log --oneline --since="30 days ago" \
  --grep="deploy\|release\|Merge.*main" | wc -l

# Or from CI: count successful production deploy jobs
# (query your CI API -- GitHub Actions, GitLab CI, etc.)

TicketPulse result (example):
  Last 30 days: 47 production deploys
  Average: 1.6 deploys per day
  Range: 0-4 deploys per day
```

### Metric 2: Lead Time for Changes

**Definition:** How long from code commit to running in production?

**Why it matters:** Short lead time means the team can respond quickly to bugs, customer feedback, and market changes. Long lead time means code queues up, merge conflicts grow, and the feedback gap widens.

```
MEASURING LEAD TIME FOR TICKETPULSE
────────────────────────────────────

Source: CI/CD pipeline timestamps

Lead time = time(PR merged) → time(running in production)

Components:
  CI pipeline (build + test):     ~8 minutes
  Staging deploy + smoke tests:   ~5 minutes
  Production deploy (rolling):    ~7 minutes
  Total:                          ~20 minutes

Note: this does NOT include PR review time. DORA measures
from commit (or merge) to production, not from "first line
written" to production. Review time is a separate metric.

TicketPulse result:
  Median lead time: 22 minutes
  P90 lead time: 45 minutes (when staging tests flake)
```

### Metric 3: Mean Time to Recovery (MTTR)

**Definition:** How long from incident detection to service restored?

**Why it matters:** Failures are inevitable. MTTR measures how quickly the team can recover. A team with a 30-minute MTTR can afford to move fast because recovery is cheap. A team with an 8-hour MTTR must move slowly because every failure is expensive.

```
MEASURING MTTR FOR TICKETPULSE
──────────────────────────────

Source: incident log + status page history

For each incident:
  recovery_time = time(resolved) - time(detected)

TicketPulse incidents (last 90 days):
  Incident 1: 30 minutes (the payment-service index issue, M73)
  Incident 2: 12 minutes (Redis connection pool exhaustion)
  Incident 3: 55 minutes (Kafka consumer rebalance storm)
  Incident 4: 8 minutes  (bad feature flag config)

  MTTR = average = (30 + 12 + 55 + 8) / 4 = 26.25 minutes
  Median MTTR = 21 minutes
```

### Metric 4: Change Failure Rate (CFR)

**Definition:** What percentage of deployments cause an incident or require rollback?

**Why it matters:** High deployment frequency is only good if the deploys are safe. CFR measures the quality of the release process. A team that deploys 10 times a day with a 30% failure rate is not "fast" — it is reckless.

```
MEASURING CFR FOR TICKETPULSE
─────────────────────────────

Source: deploy log + incident log correlation

Total deploys (last 90 days): 141
Deploys that caused incidents: 3
Deploys that required rollback: 5
(some overlap -- 2 incidents required rollback)

Unique failed deploys: 6
CFR = 6 / 141 = 4.3%
```

---

## DORA Benchmarks

### Where Does TicketPulse Fall?

```
DORA BENCHMARKS (2023 State of DevOps Report)
══════════════════════════════════════════════

Metric              │ Elite        │ High          │ Medium        │ Low
────────────────────┼──────────────┼───────────────┼───────────────┼───────────
Deployment Freq     │ On-demand    │ Daily to      │ Weekly to     │ Monthly to
                    │ (multiple/   │ weekly        │ monthly       │ every 6
                    │ day)         │               │               │ months
────────────────────┼──────────────┼───────────────┼───────────────┼───────────
Lead Time           │ < 1 hour     │ 1 day to      │ 1 week to     │ 1 month to
                    │              │ 1 week        │ 1 month       │ 6 months
────────────────────┼──────────────┼───────────────┼───────────────┼───────────
MTTR                │ < 1 hour     │ < 1 day       │ < 1 week      │ 1 week to
                    │              │               │               │ 1 month
────────────────────┼──────────────┼───────────────┼───────────────┼───────────
Change Failure Rate │ 0-15%        │ 16-30%        │ 16-30%        │ 16-30%
                    │              │               │               │
────────────────────┴──────────────┴───────────────┴───────────────┴───────────


TICKETPULSE SCORECARD
═════════════════════

Metric              │ Value          │ Rating
────────────────────┼────────────────┼────────
Deployment Freq     │ 1.6/day        │ ELITE
Lead Time           │ 22 min median  │ ELITE
MTTR                │ 26 min median  │ ELITE
Change Failure Rate │ 4.3%           │ ELITE

Overall: ELITE performer
```

TicketPulse scores Elite across the board. This is partly because the team invested in CI/CD (L2-M43), observability (L2-M48-50), and incident response (L3-M73). It is also partly because the system is still small enough that complexity has not caught up with them.

---

## 🛠️ Build: A DORA Measurement Dashboard

You do not need expensive tools to track DORA. A script querying git and your CI system is enough to start. Let us build one.

### The Git-Based Baseline

```bash
#!/bin/bash
# dora-metrics.sh -- calculate DORA metrics from git history

DAYS=${1:-30}
SINCE="$DAYS days ago"

echo "DORA Metrics for the last $DAYS days"
echo "======================================"

# --- Metric 1: Deployment Frequency ---
echo ""
echo "1. DEPLOYMENT FREQUENCY"
echo "------------------------"
DEPLOYS=$(git log --oneline --since="$SINCE" --first-parent main \
  --grep="chore(release)\|Merge.*to.*main\|deploy" | wc -l | tr -d ' ')
FREQ=$(echo "scale=2; $DEPLOYS / $DAYS" | bc)
echo "   Total deploys: $DEPLOYS in $DAYS days"
echo "   Average:       $FREQ deploys/day"
if (( $(echo "$FREQ >= 1" | bc -l) )); then
  echo "   Rating:        ELITE (>= 1/day)"
elif (( $(echo "$FREQ >= 0.14" | bc -l) )); then
  echo "   Rating:        HIGH (>= 1/week)"
else
  echo "   Rating:        MEDIUM or LOW"
fi

# --- Metric 2: Lead Time (approximation from merge commits) ---
echo ""
echo "2. LEAD TIME FOR CHANGES (last 10 merges)"
echo "------------------------------------------"
git log --merges --since="$SINCE" --first-parent main \
  --format="%ci %s" | head -10 | while IFS= read -r line; do
  echo "   $line"
done
echo ""
echo "   (For precise lead time: integrate with CI/CD API)"
echo "   (Lead time = merge timestamp - first commit in PR)"

# --- Metric 3 & 4: MTTR and CFR require external data ---
echo ""
echo "3. MTTR and 4. CFR"
echo "-------------------"
echo "   These require incident tracking data."
echo "   Query your incident log system:"
echo ""
echo "   MTTR = AVG(resolved_at - detected_at) per incident"
echo "   CFR  = COUNT(deploys_causing_incident) / COUNT(total_deploys)"
echo ""
echo "   Export from PagerDuty/OpsGenie/linear and join with deploy log."
```

### The Grafana Dashboard Query

If you have Prometheus + Grafana, expose these as metrics:

```yaml
# In your CI/CD pipeline, push deploy events to a metrics endpoint
# POST /api/internal/metrics/deploy
# { "service": "order-service", "version": "1.2.3", "status": "success" }

# Prometheus metric:
# ticketpulse_deploys_total{service, status}
# ticketpulse_deploy_lead_time_seconds{service}
```

```
Grafana Dashboard Panels:

Panel 1: Deployment Frequency (time series)
  Query: rate(ticketpulse_deploys_total{status="success"}[7d]) * 86400

Panel 2: Lead Time Distribution (heatmap)
  Query: histogram_quantile(0.50, ticketpulse_deploy_lead_time_seconds)
  Query: histogram_quantile(0.95, ticketpulse_deploy_lead_time_seconds)

Panel 3: MTTR Trend (time series)
  Query: avg_over_time(ticketpulse_incident_duration_seconds[30d])

Panel 4: Change Failure Rate (gauge)
  Query: rate(ticketpulse_deploys_total{status="failed"}[30d]) /
         rate(ticketpulse_deploys_total[30d]) * 100
```

### 📐 Exercise: Calculate Your Real Numbers

Before reading further, go calculate TicketPulse's actual DORA numbers:

```bash
# Step 1: Count deploys
cd /path/to/ticketpulse
git log --oneline --since="30 days ago" --first-parent main | wc -l

# Step 2: Check recent PR lead times
# Go to GitHub → Insights → Pull Requests
# Note the median and P90 time to merge

# Step 3: Count incidents (check your incident log or Slack #incidents channel)
# Note: time detected, time resolved for each

# Step 4: Count failed deploys (check CI/CD → failed deploy runs)
```

Write your numbers here:
- Deployment frequency: ___ per day
- Median lead time: ___ minutes
- MTTR (if any incidents): ___ minutes
- Change failure rate: ___% 

Compare to the DORA benchmarks. Where are you Elite? Where are you High or Medium? The gap is your next engineering investment.

---

## The SPACE Framework

### Beyond DORA: A Holistic View

DORA measures delivery performance. But engineering effectiveness has other dimensions. The SPACE framework (developed at GitHub and Microsoft Research, 2021) adds:

```
SPACE FRAMEWORK
═══════════════

S — Satisfaction & Well-being
  Are engineers happy? Engaged? Burned out?
  Measure: survey (quarterly), retention rate, on-call burden
  TicketPulse: "On a 1-5 scale, how sustainable is your current workload?"

P — Performance
  What outcomes does the team deliver?
  Measure: features shipped, bugs resolved, customer impact
  Not the same as "activity" -- performance measures results, not effort
  TicketPulse: "Did the last sprint's work move a business metric?"

A — Activity
  Observable actions: commits, PRs, deploys, code reviews
  WARNING: the easiest to measure and the most dangerous to optimize
  TicketPulse: "How many PRs did each engineer review this week?"
  (This is a signal, not a target)

C — Communication & Collaboration
  How well does the team share knowledge and coordinate?
  Measure: PR review turnaround, meeting load, documentation quality
  TicketPulse: "Average time from PR opened to first review?"

E — Efficiency & Flow
  Can engineers get into flow state? How much friction is there?
  Measure: CI wait time, environment setup time, context-switch frequency
  TicketPulse: "How long does it take a new engineer to make their first commit?"
```

### Combining DORA and SPACE

```
DORA tells you HOW FAST the team delivers.
SPACE tells you HOW HEALTHY the team is while delivering.

A team with Elite DORA scores but low Satisfaction is
sprinting toward burnout. The DORA numbers will eventually
collapse because the team will.

A team with high Satisfaction but Low DORA scores is
comfortable but not delivering value. They need to invest
in CI/CD, testing, and deployment practices.

The goal: Elite DORA + healthy SPACE = sustainable high performance.
```

### 📐 Exercise: SPACE Survey

Send this survey to your team (3 minutes per person):

```
SPACE QUARTERLY SURVEY
──────────────────────

[Satisfaction] On a scale of 1-5, how sustainable is your workload?
1=Burnout risk  5=Very sustainable

[Satisfaction] Do you feel your work is meaningful and impactful?
1=Not at all  5=Absolutely

[Performance] Did the work you shipped last sprint move a real user metric?
1=No clear impact  5=Clear, measurable impact

[Communication] How long does it typically take to get a code review?
1=Days  2=Same day  3=Hours  4=Under 1 hour  5=Under 30 min

[Efficiency] How often are you interrupted during deep focus work?
1=Constantly  5=Rarely or never

[Efficiency] How much time do you spend on environment/tooling issues per week?
1=>4 hours  2=2-4 hours  3=1-2 hours  4=30-60 min  5=<30 min
```

Average the scores per dimension. Any dimension below 3.0 is an area to address before it shows up in your DORA numbers.

---

## Goodhart's Law

### The Danger of Metric-Driven Management

> "When a measure becomes a target, it ceases to be a good measure."
> — Charles Goodhart (1975)

```
GOODHART'S LAW IN ENGINEERING
═════════════════════════════

IF you tell engineers "increase deployment frequency":
  THEN they will split PRs into tiny changes, deploy trivially,
  and count config changes as "deploys."
  RESULT: the number goes up, but value delivered does not.

IF you tell engineers "reduce lead time":
  THEN they will skip code review, reduce test coverage,
  and merge directly to main.
  RESULT: lead time drops, but quality drops faster.

IF you tell engineers "reduce change failure rate":
  THEN they will stop deploying risky changes, batch everything
  into massive quarterly releases, and under-report incidents.
  RESULT: CFR looks great on paper; actual reliability is worse.
```

### How to Use Metrics Safely

```
SAFE METRIC PRACTICES
─────────────────────

1. MEASURE, DO NOT TARGET
   Track DORA metrics to understand trends. Do not set them
   as individual performance goals. Teams optimize for what
   is measured, even when it hurts.

2. USE MULTIPLE METRICS TOGETHER
   Deployment frequency alone is meaningless. Pair it with
   change failure rate. Fast + safe = good. Fast + broken = bad.

3. LOOK FOR TRENDS, NOT ABSOLUTES
   "Our lead time increased from 20 min to 45 min" is a signal
   to investigate (flaky tests? long reviews? complex changes?).
   "Our lead time is 22 minutes" is just a number.

4. NEVER USE METRICS TO COMPARE INDIVIDUALS
   "Alice deploys 3x more than Bob" tells you nothing about
   value. Maybe Alice is making trivial changes and Bob is
   doing the hard architectural work.

5. LET TEAMS OWN THEIR METRICS
   Teams should track their own DORA metrics, identify their
   own bottlenecks, and propose their own improvements. Top-down
   metric mandates backfire.
```

---

## 📐 Design: Moving from High to Elite

If TicketPulse were scoring "High" instead of "Elite," what would you change?

```
IMPROVEMENT PLAN: HIGH → ELITE
═══════════════════════════════

Deployment Frequency: weekly → daily
  □ Reduce batch size (smaller PRs, single-concern changes)
  □ Automate more of the deploy pipeline (remove manual gates)
  □ Implement trunk-based development (short-lived branches)
  □ Add feature flags to decouple deploy from release

Lead Time: 1 day → 1 hour
  □ Parallelize CI steps (tests + lint + security scan)
  □ Add auto-merge for PRs with 2 approvals + green CI
  □ Pre-build Docker images on feature branches
  □ Reduce test suite time (faster tests, smarter test selection)

MTTR: 4 hours → 30 minutes
  □ Better alerting (faster detection)
  □ Runbooks for common failure modes
  □ Automated rollback on error rate spike
  □ Practice incident response regularly (M73)

Change Failure Rate: 20% → <10%
  □ Better test coverage (especially integration tests)
  □ Canary deployments (1% → 10% → 50% → 100%)
  □ Pre-production environment that mirrors production
  □ Feature flags to disable broken features without rollback
```

### 🛠️ Hands-On: Reduce Lead Time by 30%

Lead time has four components. Let us measure and attack each:

```bash
# Component 1: CI pipeline time
# Check recent CI run durations
gh run list --workflow=ci.yml --limit=20 --json durationMs \
  | jq '[.[].durationMs] | add / length / 1000 | . / 60 | "Average CI: \(.) minutes"'

# Component 2: Code review wait time
# From GitHub:
gh pr list --state=closed --limit=20 \
  --json createdAt,mergedAt,reviews \
  | jq '.[] | {
    pr: .number,
    created: .createdAt,
    merged: .mergedAt
  }'

# Component 3: Deploy pipeline time
# Check deploy workflow durations
gh run list --workflow=deploy.yml --limit=20 --json durationMs \
  | jq '[.[].durationMs] | add / length / 1000 | . / 60 | "Average deploy: \(.) minutes"'
```

**Common quick wins for each component:**

| Component | Typical Duration | Quick Win |
|---|---|---|
| CI pipeline | 8-15 min | Parallelize test jobs by splitting test files across runners |
| Code review | Hours to days | Implement a review turnaround SLO (e.g., first review within 2 hours) |
| Staging smoke tests | 3-8 min | Run only critical path tests in staging; full suite runs nightly |
| Production deploy (rolling) | 5-15 min | Optimize readiness probe timing; eliminate unnecessary delays |

If you parallelize CI across 4 runners and your test suite currently takes 12 minutes, it should now take ~3 minutes. Lead time drops from 22 minutes to ~13 minutes — a 40% improvement with one change.

---

## The Anti-Patterns: How Teams Game Metrics

Real examples of Goodhart's Law in action, and what to do about them.

```
ANTI-PATTERN 1: "Deployment Inflation"
──────────────────────────────────────
Symptom: Team deploys 20 times a day. Most deploys are README
  changes, config tweaks, and version bumps.
Reality: Feature delivery has not improved. The number is hollow.
Fix: Track "meaningful deploys" -- deploys that change application
  code, not metadata. Or track deployment frequency alongside
  feature throughput (features shipped per sprint).


ANTI-PATTERN 2: "MTTR Suppression"
───────────────────────────────────
Symptom: MTTR looks great because the team only declares SEV-1
  for truly catastrophic failures. Everything else is "not an incident."
Reality: Degradation goes untracked. Users are suffering but the
  metrics look clean.
Fix: Define clear severity criteria BEFORE incidents occur.
  Track SEV-1 through SEV-3. Report MTTR per severity level.


ANTI-PATTERN 3: "Lead Time Cherry-Picking"
──────────────────────────────────────────
Symptom: Large, risky PRs sit in review for weeks. Small fixes
  merge in hours. The median lead time looks elite, but the
  important work is slow.
Reality: The P90 tells the true story. If P50 is 20 min and
  P90 is 5 days, the team has a review bottleneck for complex changes.
Fix: Report P50, P90, AND P99. Track lead time per PR size bucket.


ANTI-PATTERN 4: "Change Failure Rate Avoidance"
────────────────────────────────────────────────
Symptom: CFR is 0% because the team only deploys when they are
  "100% confident." Deploys are batched into large, infrequent releases.
Reality: Each deploy is higher risk (more changes bundled). When
  a failure does happen, it is harder to identify which change caused it.
Fix: CFR should be paired with deployment frequency. Low CFR + low
  frequency = fear-driven. Low CFR + high frequency = genuinely good.
```

---

## 📐 Exercise: DORA Scenario Analysis

Work through these three scenarios. For each one, identify the DORA anti-pattern and prescribe the fix.

**Scenario A:** The engineering manager sends a weekly email celebrating the team that had the most deployments last week. One team deploys config changes (environment variable tweaks) multiple times a day to boost their score.

**Scenario B:** The on-call team decides that any user-visible degradation lasting less than 15 minutes is "not an incident" so they do not need to file a postmortem. MTTR looks great (average 8 minutes) because most incidents are never declared.

**Scenario C:** The company sets a goal of "P90 lead time under 1 hour" and ties it to the team's quarterly bonus. Within 2 months, PR size drops 70% but three major features are split across 15 tiny PRs with no clear narrative, making the codebase harder to understand and the review process fragmented.

**Discussion:** What would you do instead of setting DORA targets as individual or team performance goals? How do you create the right incentive structures?

---

## 🤔 Final Reflections

1. **Is TicketPulse's "Elite" rating real or inflated?** What happens when the team grows from 8 to 20? When the system adds 5 more services? Do the metrics hold?

2. **Which DORA metric is the HARDEST to improve?** Why? What are the structural obstacles?

3. **A manager asks you to "improve our DORA metrics." How do you respond?** What is the right way to use this request? What is the dangerous way?

4. **The SPACE framework includes Satisfaction. How do you measure that without surveys?** What signals indicate low satisfaction in a team you work with?

5. **If DORA metrics correlate with business performance, why do most companies NOT track them?** What prevents adoption?

6. **You discover your team's P90 lead time is 4 days, even though the P50 is 45 minutes.** What does this tell you? What would you investigate first?

---

## Key Terms

| Term | Definition |
|------|-----------|
| **DORA metrics** | Four key metrics (deployment frequency, lead time, MTTR, change failure rate) that measure software delivery performance. |
| **Deployment frequency** | How often an organization successfully deploys code to production. |
| **Lead time** | The elapsed time from code commit to that code running successfully in production. |
| **MTTR** | Mean Time to Recovery; the average time it takes to restore service after an incident. |
| **Change failure rate** | The percentage of deployments that result in a failure requiring remediation. |
| **SPACE framework** | A developer productivity framework measuring Satisfaction, Performance, Activity, Communication/Collaboration, and Efficiency/Flow. |
| **Goodhart's Law** | The principle that a measure ceases to be a useful indicator once it becomes a target, because people optimize for the measure rather than the underlying goal. |

## Further Reading

- **"Accelerate: The Science of Lean Software and DevOps"** by Nicole Forsgren, Jez Humble, Gene Kim — the book that established DORA metrics
- **Chapter 9 of the 100x Engineer Guide**: Engineering Leadership — DORA, SPACE, and measurement practices
- **The SPACE paper**: "The SPACE of Developer Productivity" (ACM Queue, 2021)
- **DORA annual report**: dora.dev — updated benchmarks every year
- **"Measuring Developer Productivity"** by Abi Noda (DX.dev) — practical guidance on avoiding Goodhart's Law
- **GitHub Engineering blog**: "How we use DORA metrics at GitHub" — a real implementation story
