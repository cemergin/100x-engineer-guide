# L3-M91b: Beast Mode — Incident Response Dry Run

> **Loop 3 (Mastery)** | Section 3F: Operational Readiness | ⏱️ 90 min | 🟢 Core | Prerequisites: L3-M91a (Observability Wiring), L3-M73 (Incident Response Simulation)
>
> **Source:** Chapter 36 of the 100x Engineer Guide

## What You'll Learn

- The "first 5 minutes" script for when you're paged and you're new
- The "what changed?" reflex — systematic change detection
- Rollback muscle memory — practicing before you need it
- Effective communication during incidents when you're the new person

## Why This Matters

L3-M73 taught incident response as an experienced team member. You had full context. You knew the services. You could reason about failure modes from memory. This module is different: you are the new person.

You just joined the TicketPulse team. You do not know every service intimately. You cannot recite the dependency graph from memory. You have never been paged on this system before. But you have your Beast Mode setup from L3-M91 and L3-M91a — your access is verified, your architecture map is drawn, your hotlinks page is bookmarked, and your baselines are captured.

That is enough to be useful. More than useful — that is enough to be the person who finds the problem.

The difference between a helpful new engineer and a panicking new engineer is not knowledge. It is preparation. A new engineer with a tested runbook and practiced muscle memory will outperform an experienced engineer who is winging it every time. This module builds that muscle memory.

> **Pro tip:** "The military does not wait for combat to practice combat. Pilots do not wait for engine failure to practice engine failure recovery. And you should not wait for a 2 AM page to practice incident response. The time to learn is now, when the stakes are low and the coffee is hot."

---

### 🤔 Prediction Prompt

Before starting the dry run, think: as the new person on the team, what is your biggest fear when the pager fires? Is it not knowing where to look, not knowing what to do, or not knowing how to communicate? This module addresses all three.

## The Scenario

**You are five days into your TicketPulse rotation.** You completed your Beast Mode setup in L3-M91 and L3-M91a. You have access, you have your architecture map, you have your hotlinks page, and you know what normal looks like on the dashboards.

Your phone buzzes at 10:17 AM on a Tuesday:

```
🔴 ALERT [CRITICAL]: Purchase success rate below threshold
   Current: 87.3% | Threshold: 95.0%
   Duration: 3 minutes
   Dashboard: https://grafana.ticketpulse.dev/d/purchases

🟡 ALERT [WARNING]: Order service p99 latency elevated
   Current: 4.8s | Threshold: 2s
   Dashboard: https://grafana.ticketpulse.dev/d/latency
```

Slack lights up in #ticketpulse-incidents:

> **@oncall-bot**: Purchase success rate alert firing. Current on-call: **you**.

You are the on-call engineer. You are new. The clock is ticking.

---

## Phase 1: The "What Changed?" Drill (~25 min)

### 🐛 Debug: Systematic Investigation Under Pressure

<details>
<summary>💡 Hint 1: "What changed?" beats "What broke?"</summary>
Run `gh run list --limit 5` and `kubectl rollout history` before reading any logs. If a deployment landed in the last 30 minutes, that is your prime suspect. Correlate the deploy timestamp with the alert start time on Grafana.
</details>

<details>
<summary>💡 Hint 2: Spend 60 seconds per check, then move on</summary>
Set a literal timer. If the deploy history looks clean, check config changes, then traffic spikes, then dependency health. The checklist order matters -- most incidents are caused by things that changed, not things that were always broken.
</details>


The single most powerful question during any incident is: **what changed?** Systems do not break spontaneously. Something changed — a deploy, a config update, a traffic spike, a dependency failure, a certificate expiry. Your job is to find it, fast.

You have 5 minutes. Start a timer now.

**Step 1 — Open your hotlinks page.** This is the page you built in L3-M91a. Open it immediately. Do not type URLs from memory. Do not search Slack history for dashboard links. Open the bookmarked hotlinks page.

```bash
# Start the clock
time_start=$(date +%s)
echo "Investigation started at $(date)"

# Open your hotlinks page (browser bookmark or):
open docs/beast-mode-hotlinks.md
```

**Step 2 — Run through the "What Changed?" checklist.** Check each item in order. Do not skip ahead. Do not go down rabbit holes. Spend no more than 60 seconds on each check.

```
"WHAT CHANGED?" INVESTIGATION CHECKLIST
═══════════════════════════════════════════════════════════════════════════
Check                     │ How to Check                    │ Finding
══════════════════════════╪═════════════════════════════════╪════════════
1. Recent deployments?    │ gh run list --limit 5           │
                          │ kubectl rollout history         │
──────────────────────────┼─────────────────────────────────┼────────────
2. Config changes?        │ git log --oneline -5 config/    │
                          │ kubectl get configmap -o yaml   │
──────────────────────────┼─────────────────────────────────┼────────────
3. Traffic pattern shift? │ Grafana: request rate panel     │
                          │ Compare to baseline from M91a   │
──────────────────────────┼─────────────────────────────────┼────────────
4. Dependency health?     │ Payment provider status page    │
                          │ Database connection pool panel   │
                          │ Kafka broker health panel        │
──────────────────────────┼─────────────────────────────────┼────────────
5. Error rate by service? │ Grafana: per-service error rate │
                          │ Which service spiked first?      │
──────────────────────────┼─────────────────────────────────┼────────────
6. Resource exhaustion?   │ kubectl top pods -n ticketpulse │
                          │ CPU, memory, disk, connections   │
──════════════════════════╧═════════════════════════════════╧════════════
```

**Step 3 — Investigate using your actual tooling.** Run the commands. Check the dashboards. For this drill, simulate the following scenario data:

The simulated environment shows:
- A deployment to `order-service` happened 8 minutes ago (commit `a3f7c2d`: "optimize database query caching")
- Request rate is normal (within baseline from your M91a capture)
- Payment provider status page shows all green
- Database connection pool is at 73% utilization (baseline was 45%)
- Order service error logs show: `ERROR: relation "order_cache" does not exist`
- Kafka consumer lag is climbing: 12,000 messages (baseline was <500)

```bash
# Simulated commands — in a real scenario you would run these live

# Check recent deployments
gh run list --limit 5
# Output shows: order-service deploy completed 8 min ago

# Check deployment diff
git log --oneline -3 origin/main
# a3f7c2d optimize database query caching
# b1e9f4a update payment timeout config
# c8d2a1b add purchase analytics endpoint

# Check order-service logs
kubectl logs -n ticketpulse deployment/order-service --tail=50 | grep ERROR
# ERROR: relation "order_cache" does not exist
# ERROR: relation "order_cache" does not exist
# ERROR: relation "order_cache" does not exist

# Check database connections
kubectl exec -n ticketpulse deployment/postgres -- psql -c "SELECT count(*) FROM pg_stat_activity;"
# count: 73 (max pool: 100)
```

**Step 4 — Fill out the Investigation Summary.** Stop your timer. Record your findings.

```
INVESTIGATION SUMMARY
═══════════════════════════════════════════════════════════════════════
Time to first finding:        _____ seconds
Total investigation time:     _____ seconds
Root cause hypothesis:        _____________________________________
Confidence (1-5):             _____
Evidence:
  1. _______________________________________________
  2. _______________________________________________
  3. _______________________________________________

Recommended action:           _____________________________________
═══════════════════════════════════════════════════════════════════════
```

For this scenario, the expected root cause is: the recent `order-service` deployment (commit `a3f7c2d`) references a database table `order_cache` that does not exist — likely a missing migration. The deploy introduced a code path that queries a table that was never created.

**Step 5 — Compare to your L3-M73 experience.** When you did L3-M73 (Incident Response Simulation), you investigated a similar scenario as an experienced team member. Compare:

```
INVESTIGATION COMPARISON
═══════════════════════════════════════════════════════════════════════
Metric                      │ L3-M73 (Experienced) │ L3-M91b (New + Setup)
════════════════════════════╪══════════════════════╪══════════════════════
Time to open dashboards     │                      │
Time to first hypothesis    │                      │
Number of dead-end checks   │                      │
Confidence in root cause    │                      │
Overall investigation time  │                      │
═══════════════════════════════════════════════════════════════════════
```

### 🤔 Reflect

> How did having the hotlinks page and baselines from M91a affect your investigation speed? Did you feel the difference compared to L3-M73, where you had more context but possibly less structure? Which approach was faster — deep knowledge or systematic checklists?

---

## Phase 2: Rollback Practice (~30 min)

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Build: Three Rollback Methods, Timed

<details>
<summary>💡 Hint 1: Know the previous good image tag BEFORE you need it</summary>
Run `kubectl rollout history deployment/order-service -n ticketpulse` now and bookmark the output format. During an incident, `kubectl rollout undo` is one command -- but only if you trust the previous revision. Verify it deploys cleanly in a dry run today.
</details>

<details>
<summary>💡 Hint 2: Feature flag toggle is fastest but only works if the flag exists</summary>
Check which TicketPulse features are behind flags right now. If the broken code path is not flagged, your options are git-revert-through-CI (safe, slow) or `kubectl set image` to the previous tag (fast, skips tests). Pick based on severity.
</details>


You identified the root cause: a bad deployment. Now you need to fix it. There are multiple ways to roll back, and each has different tradeoffs. You are going to practice all three so that when it matters, you do not have to think — you just execute.

For each method, you will:
1. Execute the rollback
2. Time how long it takes from command to verified effect
3. Verify the rollback worked
4. Document the exact steps in your personal runbook

**Method 1: Git Revert + CI/CD Pipeline**

This is the safest method — it creates a forward-moving commit that undoes the bad change, then deploys through the normal pipeline.

```bash
# Step 1: Revert the bad commit
git revert a3f7c2d --no-edit
# Creates a new commit that undoes the changes

# Step 2: Push through CI/CD
git push origin main
# Triggers the normal CI/CD pipeline

# Step 3: Monitor the pipeline
gh run watch
# Wait for build, test, deploy stages

# Step 4: Verify the rollback
kubectl get pods -n ticketpulse -w
# Watch for new pods rolling out

# Step 5: Confirm the fix
# Check purchase success rate on Grafana
# Check order-service logs — no more "relation does not exist" errors
kubectl logs -n ticketpulse deployment/order-service --tail=10 | grep ERROR
# Should return nothing
```

**Expected time**: 5-15 minutes (depends on CI/CD pipeline speed)
**When to use**: When you have time and want a clean git history
**Risk**: Pipeline might fail, adding delay

**Method 2: Redeploy Previous Docker Image**

This bypasses CI/CD entirely and deploys the last known good image directly. Faster, but you are skipping the test stage.

```bash
# Step 1: Find the previous image tag
kubectl get deployment order-service -n ticketpulse \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
# Output: registry.example.com/order-service:a3f7c2d

# Step 2: Find the last known good image tag
# The commit before a3f7c2d was b1e9f4a
kubectl set image deployment/order-service \
  order-service=registry.example.com/order-service:b1e9f4a \
  -n ticketpulse

# Step 3: Watch the rollout
kubectl rollout status deployment/order-service -n ticketpulse
# Waiting for rollout to finish...

# Step 4: Verify the rollback
kubectl get pods -n ticketpulse -l app=order-service
# All pods should be Running with 0 restarts

# Step 5: Confirm the fix
# Check purchase success rate is recovering
# Check error logs are clean
```

**Expected time**: 1-3 minutes
**When to use**: When the incident is severe and you need fast recovery
**Risk**: Skips CI tests, image must exist in registry

**Method 3: Feature Flag Toggle**

If the bad code path is behind a feature flag, this is the fastest method — no deployment needed at all.

```bash
# Step 1: Check if the feature is flagged
# In TicketPulse, feature flags are in config/feature-flags.yml
# or managed via a feature flag service

# Step 2: Disable the flag
# Option A: Config file approach
# Edit config/feature-flags.yml:
#   order_cache_optimization:
#     enabled: false

# Option B: Environment variable approach
kubectl set env deployment/order-service \
  FEATURE_ORDER_CACHE=false -n ticketpulse

# Option C: Feature flag service API
curl -X PATCH https://flags.ticketpulse.dev/api/flags/order_cache_optimization \
  -H "Authorization: Bearer $FLAG_API_TOKEN" \
  -d '{"enabled": false}'

# Step 3: Verify the flag took effect
kubectl logs -n ticketpulse deployment/order-service --tail=5
# Should see: "Feature order_cache_optimization disabled"

# Step 4: Confirm the fix
# Check purchase success rate is recovering
# Error logs should stop showing "relation does not exist"
```

**Expected time**: 30 seconds to 2 minutes
**When to use**: When the problematic code path is behind a flag
**Risk**: Only works if the feature was flagged; partial rollback only

**Record your results:**

```
ROLLBACK TIMING RESULTS
═══════════════════════════════════════════════════════════════════════════
Method              │ Time to Execute │ Time to Verify │ Total │ Notes
════════════════════╪═════════════════╪════════════════╪═══════╪══════════
Git revert + CI/CD  │                 │                │       │
Previous Docker tag │                 │                │       │
Feature flag toggle │                 │                │       │
═══════════════════════════════════════════════════════════════════════════

Fastest method:      _______________
Most reliable method: _______________
My default choice:   _______________
Reason:              _______________________________________________
```

### 🤔 Reflect

> Which method felt most comfortable? Which would you choose at 2 AM with limited context? Is there ever a reason to choose the slower git revert method during an active incident? (Hint: consider what happens when you need to deploy a fix on top of the rollback.)

---

## Phase 3: Write Your Personal Runbook (~35 min)

### 📐 Design: The Document You Open at 2 AM

<details>
<summary>💡 Hint 1: Structure it as a decision tree, not a reference page</summary>
Start with "Is the alert about latency, errors, or saturation?" and branch from there. Sleep-deprived you needs a flowchart that narrows the problem space, not a flat list of every possible command.
</details>

<details>
<summary>💡 Hint 2: Include the rollback commands verbatim with real service names</summary>
Your runbook should have `kubectl rollout undo deployment/order-service -n ticketpulse` as a copy-paste line, not "run the rollback command for the affected service." Zero thinking required at 2 AM is the goal.
</details>


Everything you practiced in Phase 1 and Phase 2 needs to be captured in a single document — your personal incident response runbook. This is not a team runbook (those exist too). This is YOUR runbook, tailored to YOUR level of context, YOUR hotlinks, and YOUR muscle memory.

This is the document you open when your phone buzzes at 2 AM and you are half asleep. It needs to be clear enough that sleep-deprived you can follow it without thinking.

**Step 1 — Create the runbook file.**

```bash
mkdir -p docs/runbooks
touch docs/runbooks/personal-incident-runbook.md
```

**Step 2 — Build your runbook using this template.** Fill in every field with real values from your TicketPulse setup. Do not leave placeholders — this document must be immediately usable.

```markdown
# Personal Incident Response Runbook — TicketPulse

> Owner: [YOUR NAME]
> Last updated: [DATE]
> Last tested: [DATE]

---

## The First 5 Minutes

When paged, follow this script in order. Do not skip steps.

### Minute 0-1: Acknowledge and Orient
- [ ] Acknowledge the alert (Slack react or PagerDuty ack)
- [ ] Open Beast Mode hotlinks page: [BOOKMARK / URL]
- [ ] Open the alerting dashboard linked in the alert
- [ ] Post in #ticketpulse-incidents:
      "Acknowledged. Investigating now. Will update in 5 minutes."

### Minute 1-3: What Changed?
- [ ] Check recent deployments: `gh run list --limit 5`
- [ ] Check config changes: `git log --oneline -5 config/`
- [ ] Check traffic patterns: compare Grafana request rate to baseline
- [ ] Check dependency status: payment provider, database, Kafka
- [ ] Check per-service error rates: which service spiked first?
- [ ] Check resource usage: `kubectl top pods -n ticketpulse`

### Minute 3-5: Hypothesis and Action
- [ ] Write down root cause hypothesis
- [ ] If deployment-related → go to **Rollback Procedures**
- [ ] If dependency-related → go to **Dependency Failures**
- [ ] If traffic-related → go to **Traffic Surge Response**
- [ ] If unknown → escalate (see **Escalation Contacts**)
- [ ] Post update in #ticketpulse-incidents:
      "Investigating [SYMPTOM]. Hypothesis: [HYPOTHESIS].
       Checking [NEXT STEP]. Next update in 10 minutes."

---

## The "What Changed?" Checklist

| Check | Command / Dashboard | Expected Normal | Current |
|-------|-------------------|-----------------|---------|
| Deployments (last 2h) | `gh run list --limit 10` | 0-2 per day | |
| Config changes | `git log --oneline -10 config/` | Infrequent | |
| Request rate | Grafana: system overview | [YOUR BASELINE] rps | |
| Error rate | Grafana: system overview | <0.1% | |
| p99 latency | Grafana: system overview | [YOUR BASELINE] ms | |
| DB connections | Grafana: database panel | [YOUR BASELINE]% pool | |
| Kafka consumer lag | Grafana: Kafka panel | <500 messages | |
| Pod restarts | `kubectl get pods -n ticketpulse` | 0 recent restarts | |

---

## Rollback Procedures

### Option A: Git Revert (Safest, ~5-15 min)
```
git revert [BAD_COMMIT] --no-edit
git push origin main
gh run watch
kubectl rollout status deployment/[SERVICE] -n ticketpulse
```
**Verify:** Check error rate dropping, success rate recovering.

### Option B: Previous Image (Fast, ~1-3 min)
```
kubectl set image deployment/[SERVICE] \
  [SERVICE]=registry.example.com/[SERVICE]:[PREVIOUS_TAG] \
  -n ticketpulse
kubectl rollout status deployment/[SERVICE] -n ticketpulse
```
**Verify:** New pods running, errors stopped.

### Option C: Feature Flag (Fastest, ~30 sec)
```
kubectl set env deployment/[SERVICE] \
  FEATURE_[FLAG_NAME]=false -n ticketpulse
```
**Verify:** Feature disabled in logs, errors stopped.

### Option D: Full Kubernetes Rollback (Emergency)
```
kubectl rollout undo deployment/[SERVICE] -n ticketpulse
kubectl rollout status deployment/[SERVICE] -n ticketpulse
```
**Verify:** Previous ReplicaSet active, pods healthy.

---

## Communication Templates

### Initial Acknowledgment
> Acknowledged [ALERT_NAME]. Investigating now. Will update in 5 minutes.

### First Update (after investigation)
> Investigating [SYMPTOM] affecting [IMPACT].
> Hypothesis: [ROOT CAUSE HYPOTHESIS].
> Action: [WHAT YOU ARE DOING].
> Next update in [X] minutes.

### Rollback Initiated
> Initiating rollback of [SERVICE] from [BAD_VERSION] to [GOOD_VERSION].
> Method: [git revert / image rollback / feature flag].
> Expected recovery time: [X] minutes.
> Will confirm when metrics recover.

### Resolution
> [SERVICE] recovered. Purchase success rate back to [X]%.
> Root cause: [BRIEF DESCRIPTION].
> Rollback method: [METHOD USED].
> Postmortem will be scheduled for [DATE/TIME].

### Escalation Request
> I am [YOUR NAME], new to the team, currently on-call.
> I am seeing [SYMPTOMS] starting at [TIME].
> I have checked [WHAT YOU CHECKED] and found [FINDINGS].
> I need help with [SPECIFIC ASK].
> Relevant dashboard: [URL]

---

## Escalation Contacts

| Situation | Who to Contact | How | When |
|-----------|---------------|-----|------|
| No progress after 15 min | Secondary on-call | PagerDuty escalation | When you are stuck |
| Database issues | Database owner | Slack DM + #data-team | Connection pool, replication, queries |
| Infrastructure issues | Platform team | #platform-oncall | Kubernetes, networking, DNS |
| Customer-facing outage >5 min | Incident commander | PagerDuty P1 escalation | Any SEV1 incident |
| Payment provider issues | Payments team | #payments-team | Payment failures, provider outages |
| You are unsure if it is serious | Tech lead | Slack DM | Always better to ask early |

---

## Dependency Failure Quick Reference

| Dependency | How to Check | Common Failure Modes |
|-----------|-------------|---------------------|
| PostgreSQL | `pg_stat_activity` count, connection pool panel | Pool exhaustion, long queries, replication lag |
| Kafka | Consumer lag panel, broker health | Consumer lag spike, broker offline, partition reassignment |
| Redis | `redis-cli ping`, memory panel | OOM, connection refused, high eviction rate |
| Payment Provider | Status page URL, API health check | Timeout, 5xx responses, rate limiting |
| CDN | Origin response time panel | Origin overload, cache miss spike |

```

**Step 3 — Test your runbook.** Re-run the Phase 1 scenario using ONLY your runbook. Do not refer to the module instructions. Follow your runbook step by step, as if it is 2 AM and you are reading it for the first time.

```bash
# Start the timer again
echo "Runbook test started at $(date)"

# Follow your runbook exactly as written
# Time each section
# Note any steps that are unclear or missing
```

**Step 4 — Fix any gaps you found during testing.** If a step was unclear, rewrite it. If a command was missing, add it. If the order felt wrong, rearrange it. Your runbook is a living document — it improves every time you use it.

```
RUNBOOK TESTING RESULTS
═══════════════════════════════════════════════════════════════════════
Run-through time:             _____ minutes
Steps that were unclear:      _____________________________________
Steps that were missing:      _____________________________________
Steps in the wrong order:     _____________________________________
Changes made after testing:   _____________________________________
═══════════════════════════════════════════════════════════════════════
```

### 🤔 Reflect

> Could someone else on the team use your runbook if you were unavailable? Is it specific enough to be immediately actionable, or does it still require tribal knowledge to follow? What would you add after your first real incident?

---

## Wrap-Up: Confidence Before Context

You have now completed the third stage of Beast Mode preparation:

1. **Investigation muscle memory** — you have a systematic "what changed?" drill that works even when you lack full context
2. **Rollback muscle memory** — you have practiced three rollback methods and know the time and tradeoffs of each
3. **Personal runbook** — you have a tested document that turns a 2 AM page from a panic event into a follow-the-checklist event

The lesson of this module is that **confidence comes from preparation, not from knowledge.** You will never know every corner of a system you just joined. But you can have:

- A checklist that covers the most common causes
- Rollback commands that you have already run once
- Communication templates that make you sound calm and competent
- Escalation contacts that you have already identified

That is enough. That is more than enough. That is what separates the new engineer who helps from the new engineer who freezes.

```
SELF-ASSESSMENT
═══════════════════════════════════════════════════════════════════════
Area                                     │ Confidence (1-5)
═════════════════════════════════════════╪══════════════════
I can investigate an incident in <5 min  │
I know three rollback methods by heart   │
My personal runbook is tested & complete │
I can communicate clearly during chaos   │
I know when and how to escalate          │
═════════════════════════════════════════╧══════════════════
```

### 🤔 Final Reflection

> Compare your confidence now to when you first did L3-M73 (Incident Response Simulation). In M73, you had the advantage of experience — you knew the system. Here, you had the advantage of preparation — you had your Beast Mode setup. Which advantage mattered more? In a real incident on a system you just joined, what is the one thing you would do differently now that you have completed this dry run? Write down that one thing and put it at the top of your runbook.

---

### 🤔 Reflection Prompt

After the dry run, how did having Beast Mode preparation (access verified, dashboards bookmarked, architecture mapped) change your confidence compared to the M73 incident simulation where you had full context? Which is more important for incident response: deep system knowledge or systematic preparation?

## Further Reading

- Chapter 36: "Beast Mode" — the full philosophy behind operational readiness
- L3-M91: Beast Mode — Access & System Mapping — where you built your foundation
- L3-M91a: Beast Mode — Observability & Dashboard Wiring — where you wired in your hotlinks and baselines
- L3-M73: Incident Response Simulation — the experienced-team-member version of incident response
- L2-M47: Alerting & On-Call — the alerting rules that trigger the pages you practiced responding to
- L2-M58: Debugging in Production — techniques for investigating live system issues
---

## What's Next

In **Beast Mode — Tribal Knowledge & the Newcomer Superpower** (L3-M91c), you'll build on what you learned here and take it further.
