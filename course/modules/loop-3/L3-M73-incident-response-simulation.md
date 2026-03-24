# L3-M73: Incident Response Simulation

> **Loop 3 (Mastery)** | Section 3C: Operations & Leadership | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M58 (Debugging in Production), L2-M48-50 (Observability Stack)
>
> **Source:** Chapter 26 of the 100x Engineer Guide

## What You'll Learn

- How to run a full incident response drill from detection to postmortem
- The role structure of an incident response: Incident Commander, Communications Lead, Investigators
- How to write status page updates that reduce customer anxiety instead of increasing it
- How to conduct a blameless postmortem that produces real action items
- How time pressure changes decision-making and what you can do about it

## Why This Matters

You will be on-call. You will get paged at the worst possible time. The difference between a 15-minute incident and a 4-hour incident is not the severity of the bug -- it is the quality of the response.

TicketPulse is a global ticketing platform. When purchases fail, users lose access to events they care about. Every minute of downtime is real money and real trust. This module simulates that pressure so your first real incident is not your first time practicing the response.

> 💡 **Insight**: "Google's SRE teams run Disaster Recovery Testing (DiRT) exercises annually. They intentionally break production systems to practice their response. The chaos is planned; the learning is real."

---

## The Scenario

**It is Friday, 4:03 PM.** You are about to close your laptop for the weekend.

Your phone buzzes. Then buzzes again. Then again.

```
🔴 ALERT [CRITICAL]: Purchase success rate dropped below 95%
   Current: 85.2% | Threshold: 99.0%
   Duration: 8 minutes
   Dashboard: https://grafana.ticketpulse.dev/d/purchases

🔴 ALERT [WARNING]: Order service p99 latency > 5s
   Current: 12.4s | Threshold: 2s
   Dashboard: https://grafana.ticketpulse.dev/d/latency

🟡 ALERT [WARNING]: Kafka consumer lag increasing - order-events
   Current lag: 45,000 | Normal: < 500
   Dashboard: https://grafana.ticketpulse.dev/d/kafka
```

Twitter is lighting up:

> "Anyone else having trouble buying tickets on @TicketPulse? Getting a spinning wheel for 2 minutes then an error."

> "Just lost floor seats to the Taylor Swift tour because @TicketPulse kept timing out. Absolutely furious."

The CEO has sent a Slack message to the #engineering channel: "What is happening with purchases?"

**Your move.**

---

## Phase 1: DETECT (5 minutes)

### What the Alerts Tell You

Before you do anything, read the alerts carefully. They contain signal.

```
Alert 1: Purchase success rate at 85.2%
├── ~15% of purchases are failing
├── This started 8 minutes ago (approximately 3:55 PM)
└── Affects the purchase flow specifically (not all API endpoints)

Alert 2: Order service p99 latency at 12.4 seconds
├── The slowest 1% of order requests take 12+ seconds
├── Normal is < 2 seconds
└── The order service is involved

Alert 3: Kafka consumer lag at 45,000
├── Consumers are falling behind producers
├── The order-events topic specifically
└── Something downstream of order creation is backed up
```

### 📐 Design: Your Detection Checklist

Before opening any dashboard, write down what you know and what you need to find out.

```
KNOWN:
- Purchase success rate dropped from ~99.9% to 85.2%
- Started approximately 3:55 PM
- Order service latency is extremely high
- Kafka consumers are falling behind

UNKNOWN:
- Which region(s) are affected?
- Is this all purchases or specific event types?
- What changed at 3:55 PM? (deploy? traffic spike? external dependency?)
- Where in the purchase flow is the failure occurring?
```

### 🛠️ Build: First Grafana Investigation

Open the purchase success rate dashboard. You see:

```
Purchase Success Rate (5-minute rolling)
────────────────────────────────────────
100% ─────────────────╲
 95% ─                 ╲
 90% ─                  ╲
 85% ─                   ╲──────────────  ← you are here
 80% ─
     ──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──
     3:30 3:35 3:40 3:45 3:50 3:55 4:00
```

The drop is sharp, not gradual. This is not a slow leak -- something broke.

Check the deployment dashboard:

```
Recent Deployments
──────────────────
3:48 PM  payment-service  v2.14.3 → v2.15.0  (deployed by: deploy-bot)
3:22 PM  event-catalog    v1.8.1 → v1.8.2    (deployed by: deploy-bot)
1:15 PM  order-service    v3.2.0 → v3.2.1    (deployed by: deploy-bot)
```

**The payment service was deployed 7 minutes before the incident started.** Flag this.

### 🤔 Reflect

> What would you do differently if there were NO recent deployments? How does the investigation change when you cannot blame a deploy?

---

## Phase 2: TRIAGE (5 minutes)

### Assign Roles

In a real incident, you need role clarity immediately. Even if you are alone, assign the roles mentally.

```
INCIDENT ROLES
──────────────
Incident Commander (IC): YOU
  - Coordinates the response
  - Makes decisions about mitigation
  - Tracks the timeline
  - Does NOT debug (delegates investigation)

Communications Lead: (assign someone, or you do it)
  - Updates status page
  - Responds to CEO/stakeholders
  - Keeps the incident channel informed

Investigators: (assign 1-2 engineers)
  - Dig into dashboards, logs, traces
  - Report findings to the IC
  - Do NOT take action without IC approval
```

### Scope Assessment

Answer these questions in 2 minutes:

```
IMPACT ASSESSMENT
─────────────────
Users affected:   ~15% of purchase attempts failing
                  Estimated: 450 users in last 10 minutes
                  (based on normal purchase rate of ~50/min)

Revenue impact:   Average ticket price $85
                  ~450 failed purchases × $85 = ~$38,250 lost
                  (some users will retry; some will not)

Regions:          Check by region:
                  US-East: 84% success  ← affected
                  US-West: 85% success  ← affected
                  EU-West: 86% success  ← affected
                  ALL regions affected → not a regional issue

Services:         Order service latency high
                  Payment service just deployed
                  Kafka consumers backing up
```

### Severity Declaration

```
SEVERITY LEVELS
───────────────
SEV-1: Complete outage, all users affected
SEV-2: Major degradation, significant user impact  ← THIS ONE
SEV-3: Minor degradation, limited user impact
SEV-4: Cosmetic or low-impact issue
```

**Declare SEV-2.** Not all purchases are failing, but 15% failure rate with revenue impact and public visibility (Twitter) qualifies.

### 🛠️ Build: First Status Page Update

Write this NOW. Do not wait until you know the root cause.

```markdown
## Investigating Purchase Failures
**Status: Investigating**
**Time: 4:05 PM UTC**

We are investigating reports of ticket purchase failures.
Some users may experience errors or extended loading times
when attempting to complete a purchase.

Our engineering team is actively investigating the issue.
We will provide an update within 15 minutes.
```

**What makes this good:**
- Acknowledges the problem exists
- Describes what users are experiencing (not internal jargon)
- Sets an expectation for the next update
- Does NOT speculate about cause

**What would be bad:**
- "We are experiencing intermittent 504 errors on the order-service gRPC endpoint due to payment gateway timeout cascade" -- users do not care about your architecture.
- "A minor issue..." -- do not minimize. Users know it is not minor.

---

## Phase 3: INVESTIGATE (15 minutes)

### Following the Trace

You pull a distributed trace for a failed purchase:

```
TRACE: purchase-attempt-a8f3c2d1 (FAILED - 14.2s)
───────────────────────────────────────────────────

[api-gateway]     0ms    → 14,200ms  (total)
  │
  ├─[order-service]  12ms → 14,180ms  (14.1s !!!)
  │   │
  │   ├─[validate-event]     12ms → 45ms     ✅ (33ms)
  │   ├─[check-inventory]    46ms → 112ms    ✅ (66ms)
  │   ├─[reserve-seats]      113ms → 245ms   ✅ (132ms)
  │   ├─[process-payment]    246ms → 14,100ms ⚠️ (13.8s !!!)
  │   │   │
  │   │   └─[payment-service] 250ms → 14,098ms
  │   │       │
  │   │       ├─[validate-card]    252ms → 380ms   ✅
  │   │       ├─[fraud-check]      381ms → 920ms   ✅
  │   │       └─[charge-card]      921ms → 14,095ms ⚠️ (13.2s)
  │   │           │
  │   │           └─[db-query]     925ms → 14,090ms 💀 (13.1s)
  │   │
  │   └─[emit-order-event]   (never reached - timeout)
```

**The trace tells a clear story:**

1. The order service calls the payment service
2. The payment service's `charge-card` operation takes 13.2 seconds
3. Inside `charge-card`, a database query takes 13.1 seconds
4. The order service times out waiting for payment
5. The order event is never emitted (which explains the Kafka lag -- successful orders still emit, but volume is down)

### The Database Query

Check the payment service's slow query log:

```sql
-- This query was added in v2.15.0 (the 3:48 PM deploy)
SELECT t.*, p.*, pm.method_details
FROM transactions t
JOIN payments p ON t.payment_id = p.id
JOIN payment_methods pm ON p.method_id = pm.id
WHERE t.user_id = $1
  AND t.status IN ('completed', 'refunded', 'disputed')
ORDER BY t.created_at DESC
LIMIT 100;
```

Check the query plan:

```
Seq Scan on transactions  (cost=0.00..847293.12 rows=45123 width=284)
  Filter: (user_id = $1 AND status = ANY('{completed,refunded,disputed}'))
  Rows Removed by Filter: 12847291
```

**Sequential scan on 12.8 million rows.** The `transactions` table does not have an index that covers this query. The new query was added as part of v2.15.0's "enhanced fraud detection" feature, but the migration that creates the index failed silently during deployment.

### The Cascade

Here is how a single slow query caused a platform-wide degradation:

```
ROOT CAUSE: Missing index on transactions table
    │
    ├─→ Payment service queries take 13+ seconds
    │
    ├─→ Order service times out waiting for payment (timeout: 15s)
    │     │
    │     ├─→ Order service connection pool fills up
    │     │   (all connections waiting on payment responses)
    │     │
    │     └─→ New purchase requests queue behind blocked connections
    │         │
    │         └─→ API gateway starts returning 504s
    │
    ├─→ Successful orders reduced → fewer Kafka events emitted
    │     │
    │     └─→ Kafka consumers appear "lagged" (actually just less throughput)
    │
    └─→ Users see timeouts → retry → MORE load on already-struggling system
                                      (retry storm amplifies the problem)
```

### 🛠️ Build: The Investigation Timeline

Write the timeline as you go. This becomes part of the postmortem.

```
INCIDENT TIMELINE
─────────────────
3:48 PM  payment-service v2.15.0 deployed (includes new fraud check query)
3:48 PM  Database migration for new index FAILED (migration runner error in logs)
3:55 PM  First slow queries appear (users with large transaction histories hit first)
3:58 PM  Order service connection pool at 80% utilization
4:01 PM  Connection pool saturated; new requests start queueing
4:03 PM  Alert fires: purchase success rate < 95%
4:03 PM  Alert fires: order service p99 > 5s
4:04 PM  Alert fires: Kafka consumer lag increasing
4:05 PM  IC declares SEV-2, posts first status update
4:07 PM  Trace analysis points to payment service DB query
4:12 PM  Root cause identified: missing index from failed migration
4:15 PM  (NEXT: mitigation)
```

### 🤔 Reflect

> The cascade turned a database issue into a platform-wide problem. What architectural patterns could have contained the blast radius? Think about circuit breakers, bulkheads, and timeout budgets.

---

## Phase 4: MITIGATE (10 minutes)

### The Options

You have identified the root cause. Now you need to stop the bleeding. There are several options, each with trade-offs.

```
MITIGATION OPTIONS
──────────────────

Option A: Rollback the payment service to v2.14.3
  ✅ Removes the problematic query entirely
  ✅ Known-good state
  ⚠️ Takes 3-5 minutes for rolling deployment
  ⚠️ Loses the non-broken changes in v2.15.0

Option B: Apply the missing index manually
  ✅ Fixes the root cause directly
  ⚠️ CREATE INDEX on 12.8M rows will take 5-10 minutes
  ⚠️ CREATE INDEX CONCURRENTLY is safer but slower
  ⚠️ Does not help until the index build completes

Option C: Enable circuit breaker on payment calls
  ✅ Stops the cascade immediately
  ✅ Fast (config change, no deploy)
  ⚠️ ALL purchases fail (instead of 15%)
  ⚠️ Trades partial failure for total failure

Option D: Rollback + apply index in parallel
  ✅ Immediate relief (rollback) + permanent fix (index)
  ✅ Can re-deploy v2.15.0 once index exists
  ⚠️ Requires coordinating two actions simultaneously
```

### 📐 Design: Choose Your Mitigation

**The right answer is D: rollback immediately, apply index concurrently.**

Reasoning:
- Rollback restores service within 3-5 minutes
- Index creation runs in the background and does not block the rollback
- Once the index exists, v2.15.0 can be safely re-deployed
- This is the fastest path to full recovery

```bash
# Action 1: Rollback payment service (IC approves)
kubectl rollout undo deployment/payment-service -n ticketpulse
# Verify: watch the success rate recover over 2-3 minutes

# Action 2: Apply the missing index concurrently
psql -h payment-db.ticketpulse.internal -U admin -d payments <<'SQL'
CREATE INDEX CONCURRENTLY idx_transactions_user_status_created
ON transactions (user_id, status, created_at DESC);
SQL
```

### 🛠️ Build: Status Page Updates During Mitigation

**Update 2: Identified**

```markdown
## Purchase Failures - Root Cause Identified
**Status: Identified**
**Time: 4:15 PM UTC**

We have identified the cause of the purchase failures.
A recent deployment introduced a database performance issue
that is causing some purchases to time out.

We are rolling back the change now. We expect purchases
to return to normal within 5 minutes.

Next update in 10 minutes.
```

**Update 3: Mitigating**

```markdown
## Purchase Failures - Fix In Progress
**Status: Mitigating**
**Time: 4:20 PM UTC**

The rollback is complete. Purchase success rates are
recovering. We are seeing improvement and monitoring
closely.

Some users may need to retry their purchase.

Next update in 15 minutes or when fully resolved.
```

### 🤔 Reflect

> Why was Option C (circuit breaker) the wrong choice here, even though it stops the cascade immediately? Under what circumstances WOULD you choose to break the circuit and accept total failure?

---

## Phase 5: COMMUNICATE (5 minutes)

### Stakeholder Communication

Beyond the status page, you need to communicate internally.

**To the CEO (Slack, immediately):**

```
@CEO - SEV-2 incident update:
- Purchase success rate dropped to 85% at 3:55 PM
- Root cause: a database performance issue from the 3:48 PM deploy
- We rolled back at 4:18 PM; success rate is recovering
- Estimated full recovery: 4:25 PM
- ~450 purchase attempts affected during the incident
- No data loss. Will send postmortem by Monday.
```

**To Customer Support (Slack):**

```
@support-team - Incident update:
- Purchase failures from 3:55-4:25 PM are resolved
- Users who saw errors can retry their purchase now
- No charges were made for failed purchases
- If users report duplicate charges, escalate to #payments
```

**To Engineering (incident channel):**

```
@here - Incident resolved. Quick summary:
- payment-service v2.15.0 included a new query without a required index
- The migration to create the index failed silently during deploy
- We rolled back to v2.14.3; success rate back to 99.9%
- Index is being created now; will re-deploy v2.15.0 Monday
- Postmortem scheduled for Monday 10 AM
- Action items being tracked in the postmortem doc
```

### 🛠️ Build: Resolution Status Page Update

```markdown
## Purchase Failures - Resolved
**Status: Resolved**
**Time: 4:30 PM UTC**

The purchase issue has been resolved. All systems are
operating normally.

**What happened:** A deployment at 3:48 PM UTC introduced
a database performance issue that caused some ticket purchases
to fail or time out between 3:55 PM and 4:25 PM UTC.

**Impact:** Approximately 15% of purchase attempts during
the affected period failed. No duplicate charges were made.

**Resolution:** We rolled back the deployment. If you
experienced a failed purchase, you can safely retry now.

We apologize for the inconvenience and are implementing
additional safeguards to prevent similar issues.
```

---

## Phase 6: RESOLVE (5 minutes)

### Permanent Fix

The rollback stopped the bleeding. Now apply the permanent fix.

```sql
-- 1. Verify the index was created successfully
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'transactions'
AND indexname = 'idx_transactions_user_status_created';

-- 2. Test the query with the index
EXPLAIN ANALYZE
SELECT t.*, p.*, pm.method_details
FROM transactions t
JOIN payments p ON t.payment_id = p.id
JOIN payment_methods pm ON p.method_id = pm.id
WHERE t.user_id = 12345
  AND t.status IN ('completed', 'refunded', 'disputed')
ORDER BY t.created_at DESC
LIMIT 100;

-- Expected: Index Scan (not Seq Scan), < 50ms execution time
```

### Pre-Deploy Verification

Before re-deploying v2.15.0:

```
DEPLOY CHECKLIST (before re-deploy)
────────────────────────────────────
□ Index exists and is valid (not INVALID state)
□ Query plan shows index scan (tested with EXPLAIN ANALYZE)
□ Migration runner issue diagnosed and fixed
□ Payment service has integration test for new fraud query
□ Deploy during business hours (not Friday 4 PM)
□ Canary deploy to 5% of traffic first
□ Monitor slow query log during canary
```

### 🤔 Reflect

> Why should you NOT re-deploy on Friday evening, even if the fix is verified? What does "deploy during business hours" really protect against?

---

## Phase 7: POSTMORTEM (20 minutes)

### 🛠️ Build: The Blameless Postmortem

Write the complete postmortem document. This is the most important artifact from the incident.

```markdown
# POSTMORTEM: Purchase Failures Due to Missing Database Index

**Date:** [Today's date]
**Duration:** 30 minutes (3:55 PM - 4:25 PM UTC)
**Severity:** SEV-2
**Author:** [Your name]
**Status:** Action items in progress

## Summary

A deployment of payment-service v2.15.0 at 3:48 PM included a new
database query for enhanced fraud detection. The migration to create
the required index failed silently. Without the index, the query
caused full table scans on the 12.8M-row transactions table, resulting
in 13+ second query times. This cascaded into order service timeouts,
connection pool exhaustion, and a 15% purchase failure rate.

## Impact

- **Duration:** 30 minutes
- **Users affected:** ~450 purchase attempts failed
- **Revenue impact:** ~$38,250 in failed purchases (partial recovery
  expected from retries)
- **SLA impact:** Monthly availability dropped from 99.97% to 99.93%
- **Customer impact:** Negative social media posts, support ticket spike

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 3:48 PM | payment-service v2.15.0 deployed |
| 3:48 PM | Database migration for index fails (error in migration runner) |
| 3:55 PM | First slow queries from users with large transaction history |
| 3:58 PM | Order service connection pool at 80% |
| 4:01 PM | Connection pool saturated; requests start queueing |
| 4:03 PM | Alerts fire: success rate, latency, Kafka lag |
| 4:05 PM | IC declares SEV-2, first status page update |
| 4:07 PM | Trace analysis points to payment service DB query |
| 4:12 PM | Root cause identified: missing index |
| 4:15 PM | Decision: rollback + apply index concurrently |
| 4:18 PM | Rollback initiated |
| 4:22 PM | Rollback complete, success rate recovering |
| 4:25 PM | Success rate back to 99.9%, incident resolved |

## Root Cause

The new fraud detection query (added in v2.15.0) required an index
on `transactions(user_id, status, created_at)`. The migration to
create this index was included in the deployment but failed due to
a timeout in the migration runner (default timeout: 30 seconds;
index creation on 12.8M rows: ~8 minutes).

The migration runner logged the failure but the deployment pipeline
did not treat migration failures as deployment failures. The service
started with the new code but without the required index.

## Contributing Factors

1. **Migration failures are not deployment blockers.** The pipeline
   treats migrations as best-effort, not required.

2. **No query performance testing.** The new query was not tested
   against a production-sized dataset before deployment.

3. **No slow-query alerting on payment-service.** The alert existed
   for order-service but not payment-service.

4. **Friday afternoon deploy.** Reduced team availability for
   response. No policy preventing late-week deploys.

5. **No circuit breaker between order and payment services.**
   The order service waited the full 15-second timeout for every
   payment call, exhausting its connection pool.

## What Went Well

- Alert fired within 8 minutes of impact starting
- Root cause identified within 12 minutes of alert
- Rollback was fast (4 minutes from decision to completion)
- Status page updates were timely and clear
- No data corruption or duplicate charges

## What Went Wrong

- Migration failure was not caught by the deployment pipeline
- 8-minute gap between first impact and alert (users noticed first)
- No circuit breaker prevented the cascade from payment to order
- Deploy on Friday afternoon with reduced team availability

## Action Items

| # | Action | Owner | Priority | Due |
|---|--------|-------|----------|-----|
| 1 | Make migration failures block deployments | Platform | P0 | 1 week |
| 2 | Add slow-query alert for all services | SRE | P0 | 1 week |
| 3 | Add circuit breaker between order and payment | Orders team | P1 | 2 weeks |
| 4 | Test queries against prod-size dataset in CI | Platform | P1 | 3 weeks |
| 5 | Implement deploy freeze policy (no deploys after 3 PM Friday) | Engineering | P2 | 1 week |
| 6 | Add connection pool saturation alert | SRE | P1 | 1 week |
| 7 | Reduce detection gap: alert at 1% failure rate, not 5% | SRE | P2 | 2 weeks |
```

### Blameless Postmortem Principles

Notice what the postmortem does NOT say:

- It does NOT say "Engineer X deployed without checking the migration"
- It does NOT say "The payment team should have known better"
- It does NOT say "Human error" as the root cause

Instead, it asks: **"Why did the system allow this to happen?"**

```
BLAMELESS POSTMORTEM PRINCIPLES
───────────────────────────────
1. Humans make mistakes. Systems should prevent mistakes from
   becoming incidents.

2. The person closest to the failure often has the best insight
   into what happened. Blame discourages honesty.

3. "Be more careful" is never an action item. Automated guardrails
   are.

4. Every contributing factor should map to a systemic improvement,
   not a person to reprimand.

5. The postmortem is an investment in future prevention. If people
   are afraid to report honestly, the investment is wasted.
```

---

## Full Exercise Recap

### Artifacts You Should Have Written

By the end of this module, you should have produced:

```
ARTIFACTS CHECKLIST
───────────────────
□ Detection assessment (what you know vs. what you need to find out)
□ Severity declaration with justification
□ Status page update: Investigating
□ Investigation timeline (built incrementally)
□ Cascade diagram showing how root cause propagated
□ Mitigation options analysis with trade-offs
□ Status page update: Identified
□ Status page update: Mitigating
□ Stakeholder communications (CEO, support, engineering)
□ Status page update: Resolved
□ Deploy checklist for permanent fix
□ Complete blameless postmortem with action items
```

### Time Budget (How This Maps to 75 Minutes)

```
Phase 1: DETECT         5 min
Phase 2: TRIAGE         5 min
Phase 3: INVESTIGATE   15 min
Phase 4: MITIGATE      10 min
Phase 5: COMMUNICATE    5 min
Phase 6: RESOLVE        5 min
Phase 7: POSTMORTEM    20 min
Review & Reflect       10 min
                      ───────
Total                  75 min
```

---

## 🤔 Final Reflections

1. **What was the most stressful part of this exercise?** Even simulated, which phase felt the most chaotic? Now imagine doing this at 3 AM with half the team asleep.

2. **What would have made the response faster?** Think about: runbooks, automated rollback triggers, better alerting thresholds, pre-computed blast radius maps.

3. **What single investment would prevent the most future incidents?** Not specific to this incident -- across all possible incidents, what capability would you build?

4. **How did the cascade change your thinking about service boundaries?** A missing index in one service took down purchase flow across the platform. What architectural patterns would contain this?

5. **Would you have handled this differently if it were 2 AM instead of 4 PM Friday?** If yes, what does that tell you about your team's incident readiness?

---

## Key Terms

| Term | Definition |
|------|-----------|
| **Incident commander** | The person who coordinates the response during an incident, making decisions and delegating tasks. |
| **War room** | A dedicated communication channel (physical or virtual) where the incident response team collaborates in real time. |
| **Escalation** | The process of involving additional or more senior responders when an incident exceeds the current team's capacity. |
| **Status page** | A public-facing page that communicates current system status and ongoing incidents to users. |
| **Postmortem** | A blameless review conducted after an incident to document what happened and define preventive action items. |

## Further Reading

- **Chapter 26**: Incident War Stories & Postmortem Analysis -- real-world incidents studied in depth
- **Chapter 4**: SRE principles, SLOs, and incident management frameworks
- **Google's SRE Book, Chapter 15**: "Postmortem Culture: Learning from Failure"
- **PagerDuty's Incident Response Guide**: https://response.pagerduty.com/
- **Etsy's Debriefing Facilitation Guide**: how to run effective postmortem meetings
