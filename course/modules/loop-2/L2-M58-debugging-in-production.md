# L2-M58: Debugging in Production

> **Loop 2 (Practice)** | Section 2E: Security & Quality | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M45 (Prometheus+Grafana), L2-M46 (OpenTelemetry), L2-M48 (Chaos Engineering)
>
> **Source:** Chapter 18 of the 100x Engineer Guide

## What You'll Learn

- The systematic debugging playbook for production incidents
- How to diagnose problems using ONLY observability tools (no SSH, no code access)
- How to read metrics, logs, and traces to isolate root causes
- The "5 Whys" technique for getting past symptoms to root causes
- How to handle layered failures where multiple things break simultaneously
- How to write an incident timeline as you debug

## Why This Matters

This is THE module that separates senior engineers from junior engineers. Junior engineers debug by reading code, adding print statements, and restarting services. Senior engineers debug by reading dashboards, correlating traces, and isolating variables -- because in production, you often cannot read code, cannot add print statements, and restarting services might make things worse.

TicketPulse v2 is now a distributed system with multiple services, databases, message queues, and external dependencies. When something breaks, the failure might originate in one service and manifest in another. The ability to systematically find the root cause -- under pressure, at 3 AM, with incomplete information -- is the most valuable skill in backend engineering.

> **The bigger picture:** "Amazon's CTO Werner Vogels: 'The best way to get good at debugging is to spend time debugging.' This module IS that time."

## Prereq Check

You need the full TicketPulse v2 stack running with observability:

```bash
# Verify services are running
kubectl get pods -n ticketpulse

# Verify Prometheus is collecting metrics
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets | length'

# Verify Grafana dashboards are accessible
curl -s http://localhost:3001/api/health | jq .

# Verify Jaeger is receiving traces
curl -s http://localhost:16686/api/services | jq .
```

If any of these are not running, go back to L2-M45 through L2-M48 and set them up.

---

## Part 1: The Systematic Debugging Playbook

### The Incident Scenario

It is 2:47 PM on a Thursday. You get a page:

> **ALERT: TicketPulse purchase error rate > 5% for 5 minutes**
> Dashboard: https://grafana.ticketpulse.dev/d/purchases
> On-call: You

Users are reporting that ticket purchases are failing intermittently. Some purchases succeed, some fail with a vague error. Customer support tickets are piling up.

You have:
- Grafana dashboards (metrics)
- Jaeger (distributed traces)
- Centralized logs (structured JSON)
- Kafka UI (consumer group monitoring)
- `kubectl` access (but no SSH into containers)

You do NOT have:
- Access to the source code (you are on-call for a service another team owns)
- The ability to add breakpoints or print statements
- Time to read through the codebase

Let's debug this systematically.

### Step 1: Assess Impact (2 minutes max)

Before fixing anything, understand the scope.

```
Questions to answer immediately:
├── WHO is affected?       → All users? Specific events? Specific regions?
├── WHAT is broken?        → Complete failure? Intermittent? Degraded?
├── WHEN did it start?     → Correlates with a deployment? Traffic spike?
└── HOW MANY?              → Error count, affected user count
```

**📊 Observe: Check the dashboard**

Open the Grafana purchases dashboard. Look at three things:

```
# PromQL: Current error rate
sum(rate(http_requests_total{service="purchase-service",status=~"5.."}[5m]))
/ sum(rate(http_requests_total{service="purchase-service"}[5m]))

# Expected: normally < 0.1%. Currently showing: 8.3%

# PromQL: Error rate by endpoint
sum by (path) (rate(http_requests_total{service="purchase-service",status=~"5.."}[5m]))
```

What you observe:
- Error rate spiked from 0.1% to 8.3% at 2:35 PM
- Only the `/api/purchases` endpoint is affected
- `/api/events` (read-only) is fine
- Traffic volume is normal (not a traffic spike)

**Write it down.** Start an incident timeline immediately:

```
2:47 PM - Alerted: purchase error rate > 5%
2:49 PM - Confirmed: 8.3% error rate on /api/purchases
         Only purchases affected. Event browsing normal.
         Started at ~2:35 PM. Traffic volume normal.
```

### Step 2: Check Recent Changes (3 minutes)

Most incidents are caused by a recent change.

```bash
# What was deployed recently?
kubectl -n ticketpulse rollout history deployment/purchase-service
# REVISION  CHANGE-CAUSE
# 14        image update to v2.8.1 at 2:15 PM  ← SUSPICIOUS
# 13        image update to v2.8.0

# Any other deployments around the same time?
kubectl -n ticketpulse get events --sort-by='.lastTimestamp' | tail -20
```

A deployment happened at 2:15 PM. The errors started at 2:35 PM -- a 20-minute delay. That is suspicious but not conclusive. The bug might only trigger under certain conditions that took 20 minutes to occur.

```
2:51 PM - purchase-service v2.8.1 deployed at 2:15 PM.
         Errors started 20 min later. Investigating.
```

### Step 3: Check the RED Metrics (5 minutes)

RED = Rate, Errors, Duration. Check each for every service in the purchase flow.

**📊 Observe: Grafana service-level metrics**

```
Purchase Flow:
  API Gateway → Purchase Service → Event Service (check availability)
                                 → Payment Service (charge card)
                                 → Kafka (emit purchase event)
```

For each service, check:

| Service | Request Rate | Error Rate | p99 Latency |
|---|---|---|---|
| API Gateway | Normal | Elevated (8%) | Normal |
| Purchase Service | Normal | **Elevated (8%)** | **Elevated (2.1s, normally 200ms)** |
| Event Service | Normal | Normal | **Elevated (800ms, normally 50ms)** |
| Payment Service | Normal | Normal | Normal |

Interesting: the purchase service has high latency AND errors. The event service has high latency but no errors. The payment service is fine.

```
2:54 PM - RED metrics show:
         - Purchase service: 8% error rate, p99 latency 2.1s (normally 200ms)
         - Event service: p99 latency 800ms (normally 50ms), no errors
         - Payment service: healthy
         Hypothesis: Event service slowness may be causing purchase timeouts
```

### Step 4: Check Logs (5 minutes)

Filter logs by error level for the purchase service:

```bash
# Query centralized logs (adjust for your log aggregator)
# Filter: service=purchase-service, level=error, last 30 minutes

# If using kubectl:
kubectl -n ticketpulse logs deployment/purchase-service --since=30m \
  | jq 'select(.level == "error")' | head -50
```

What you find in the logs:

```json
{
  "level": "error",
  "timestamp": "2024-03-14T14:42:17.234Z",
  "service": "purchase-service",
  "traceId": "abc123def456",
  "requestId": "req-789",
  "message": "Failed to complete purchase",
  "error": "Connection pool exhausted: all 20 connections are in use",
  "eventId": "evt-1234",
  "userId": "user-567"
}
```

```json
{
  "level": "error",
  "timestamp": "2024-03-14T14:42:18.891Z",
  "service": "purchase-service",
  "traceId": "xyz789abc012",
  "message": "Request timeout after 5000ms",
  "endpoint": "event-service/api/events/evt-5678/availability",
  "eventId": "evt-5678"
}
```

Two distinct error patterns:
1. **Connection pool exhaustion** -- the purchase service cannot get database connections
2. **Timeout calling event service** -- availability checks are timing out

```
2:57 PM - Logs reveal two problems:
         1. Database connection pool exhausted (all 20 connections in use)
         2. Calls to event-service/availability timing out (>5s)
         These may be related: slow DB queries → connections held longer → pool exhaustion
```

### Step 5: Check Traces (5 minutes)

Find a failing trace in Jaeger to see where time is spent.

Open Jaeger, search for traces where:
- Service: purchase-service
- Tag: error=true
- Min Duration: 2s

Click on a failing trace. The waterfall view shows:

```
purchase-service: POST /api/purchases  [5012ms] ❌
├── event-service: GET /api/events/evt-1234/availability  [4800ms]
│   └── postgres: SELECT tickets WHERE event_id = ... AND status = 'available'  [4750ms] ← THE BOTTLENECK
├── payment-service: POST /api/payments  [not reached - timeout]
└── kafka: produce purchase-event  [not reached]
```

The trace tells the whole story: a database query in the event service is taking 4.75 seconds. This slows down the availability check, which times out the purchase service, which exhausts the connection pool because connections are held while waiting.

```
3:00 PM - Traces show: event-service availability query taking 4.7s
         (normally <50ms). Query: SELECT available tickets for event.
         This is causing cascade: slow query → timeout → pool exhaustion
```

### Step 6: Check Dependencies (3 minutes)

The slow query points to the database. Check database health:

```bash
# Check database metrics in Grafana
# PromQL: Active connections
pg_stat_activity_count{datname="events"}

# PromQL: Query duration
pg_stat_activity_max_tx_duration{datname="events"}

# Check via kubectl if you have DB access
kubectl -n ticketpulse exec -it deployment/event-db -- \
  psql -U ticketpulse -d events -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
```

What you find:
- 45 active connections (max: 50) -- nearly exhausted
- Several connections in "active" state for 10+ seconds
- One query doing a sequential scan on the tickets table

Now check Kafka:

```bash
# Check consumer group lag
kubectl -n ticketpulse exec -it kafka-0 -- \
  kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --group purchase-processor
```

```
GROUP               TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
purchase-processor  purchase-events 0          45892           46217           325
purchase-processor  purchase-events 1          44103           44103           0
purchase-processor  purchase-events 2          43567           43567           0
```

Partition 0 has a lag of 325 messages and growing. The consumer is stuck.

```
3:03 PM - Found additional problems:
         - Event DB: 45/50 connections active, sequential scans
         - Kafka: purchase-processor consumer stuck on partition 0 (lag: 325)
```

### Step 7: Isolate (5 minutes)

You now have three problems. Let's isolate whether they are independent or connected:

**Problem 1: Event service database connection pool near exhaustion**

Check which queries are slow:

```sql
-- If you have DB access:
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC
LIMIT 10;
```

You find: queries for events with more than 1000 tickets are doing sequential scans because the query plan changes when the estimated row count crosses a threshold.

**Problem 2: Kafka consumer stuck on partition 0**

Check the consumer logs:

```bash
kubectl -n ticketpulse logs deployment/purchase-processor --since=30m \
  | jq 'select(.level == "error" or .level == "warn")' | tail -20
```

```json
{
  "level": "error",
  "message": "Failed to process purchase event",
  "error": "Event not found: evt-9999",
  "partition": 0,
  "offset": 45892
}
```

The consumer is stuck retrying a single message that references a non-existent event. It is blocking all subsequent messages on partition 0.

**Problem 3: Connection pool exhaustion on the purchase service**

This is a cascade from Problem 1. Slow event-service responses mean purchase-service connections are held for 5+ seconds instead of 200ms. At 4 requests/second, that is 20 connections held simultaneously -- exactly the pool size.

```
3:08 PM - ROOT CAUSES IDENTIFIED:
         Problem 1 (primary): Slow DB queries for high-ticket events
           → Missing index or bad query plan for events with >1000 tickets
           → Likely introduced in v2.8.1 (new query or changed WHERE clause)
         Problem 2 (independent): Kafka consumer stuck on bad message
           → Message references non-existent event, consumer retry loop
         Problem 3 (cascade): Connection pool exhaustion
           → Caused by Problem 1 (slow queries → held connections)
```

---

## Part 2: The Three-Problem Debug Exercise

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Build: Diagnose All Three Problems

<details>
<summary>💡 Hint 1: Direction</summary>
Consider the trade-offs between different approaches before choosing one.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Refer back to the patterns introduced earlier in this module.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The solution uses the same technique shown in the examples above, adapted to this specific scenario.
</details>


Now it is your turn. Set up the three problems in your TicketPulse environment and practice diagnosing them using only observability tools.

**Setting up Problem 1: Slow Database Queries**

```sql
-- In the event service database, create a scenario with a missing index
-- Add a large event with many tickets
INSERT INTO events (name, venue, date, total_tickets)
VALUES ('Stadium Concert', 'MetLife Stadium', NOW() + INTERVAL '30 days', 50000);

-- Generate 50,000 tickets for this event
INSERT INTO tickets (event_id, status, section, row_num, seat, price)
SELECT
    (SELECT id FROM events WHERE name = 'Stadium Concert'),
    CASE WHEN random() < 0.7 THEN 'available' ELSE 'sold' END,
    'Section ' || (s % 100),
    'Row ' || (s / 100),
    'Seat ' || (s % 50),
    ROUND((random() * 200 + 50)::numeric, 2)
FROM generate_series(1, 50000) s;

-- Drop the index that makes availability queries fast
-- (simulating a migration that forgot to add it for the new query)
DROP INDEX IF EXISTS idx_tickets_event_available;

-- Now availability queries for this event will sequential scan:
EXPLAIN ANALYZE
SELECT count(*) FROM tickets
WHERE event_id = (SELECT id FROM events WHERE name = 'Stadium Concert')
  AND status = 'available';
-- Expected: Seq Scan, 500ms+
```

**Setting up Problem 2: Stuck Kafka Consumer**

```typescript
// In the purchase-processor, simulate a poison message
// Produce a message referencing a non-existent event:
await producer.send({
  topic: 'purchase-events',
  messages: [{
    key: 'evt-99999',
    value: JSON.stringify({
      type: 'purchase.completed',
      eventId: 'evt-99999',  // does not exist
      userId: 'user-123',
      ticketCount: 2,
    }),
  }],
});
```

**Setting up Problem 3: Connection Pool Exhaustion**

This happens automatically as a cascade from Problem 1. When event-service queries are slow, purchase-service connections are held longer, and the pool fills up.

### Your Task

Using only these tools, diagnose all three problems and determine the fix order:
- Grafana dashboards (RED metrics, database metrics, Kafka metrics)
- Jaeger traces (find slow and failing traces)
- Centralized logs (`kubectl logs` with jq filtering)
- Kafka UI or CLI (consumer group status)

**Do not look at the source code.** Debug through observability alone.

Write an incident timeline as you go, documenting:
- What you checked
- What you found
- What you concluded
- What you will check next


<details>
<summary>💡 Hint 1: Direction</summary>
Use three different tools for three different problems: distributed tracing (Jaeger) for latency, log aggregation for errors, and metrics (Prometheus/Grafana) for resource exhaustion.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
For intermittent slowness, look at p99 latency in traces — the average may look fine while the 99th percentile is terrible. For errors, search logs by correlation ID to follow a request across services. For resource issues, check connection pool metrics and memory usage.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The three classic production problems: (1) a slow downstream dependency (visible in traces as one span taking 90% of total time), (2) a connection pool leak (visible in metrics as growing active connections that never decrease), (3) a memory leak (visible in metrics as monotonically increasing heap usage). Each requires a different tool to diagnose.
</details>

---

## Part 3: Triage and Fix Order

### 🤔 Reflect: Which Problem Do You Fix First?

This is not obvious. Think about it before reading the answer.

<details>
<summary>Recommended fix order (think first, then click)</summary>

**Fix Problem 2 first (stuck Kafka consumer).** Why?

The Kafka consumer is accumulating lag. Every minute it stays stuck, more purchase events pile up unprocessed. Those events might include things like sending confirmation emails, updating analytics, or triggering downstream workflows. The blast radius is growing.

Fix: implement a dead-letter queue (DLQ) or skip the poison message:

```bash
# Quick fix: reset the consumer offset past the bad message
kubectl -n ticketpulse exec -it kafka-0 -- \
  kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group purchase-processor --topic purchase-events \
  --reset-offsets --shift-by 1 --partition 0 --execute
```

**Fix Problem 1 second (slow database queries).**

This is the root cause of the user-facing errors. Add the missing index:

```sql
CREATE INDEX CONCURRENTLY idx_tickets_event_status
  ON tickets(event_id, status)
  WHERE status = 'available';
```

Use `CONCURRENTLY` to avoid locking the table.

**Problem 3 resolves itself** once Problem 1 is fixed. When queries are fast again, connections are released quickly, and the pool returns to normal utilization.

If Problem 3 is causing immediate harm, you can also increase the pool size as a temporary measure:

```bash
# Scale up purchase-service or increase pool size via config
kubectl -n ticketpulse set env deployment/purchase-service DB_POOL_MAX=50
```

</details>

---

## Part 4: The 5 Whys

Apply the 5 Whys technique to Problem 1:

```
1. WHY are ticket purchases failing?
   → The purchase service is timing out on event-service availability checks.

2. WHY are availability checks slow?
   → The database query is doing a sequential scan on the tickets table.

3. WHY is it doing a sequential scan?
   → There is no index on (event_id, status) for the new availability query.

4. WHY is there no index?
   → The v2.8.1 migration added a new query pattern but did not include
     the corresponding index. The previous query used a different WHERE
     clause that was covered by an existing index.

5. WHY did the missing index reach production?
   → There is no CI check that runs EXPLAIN ANALYZE on new queries.
     The existing load tests use events with < 100 tickets, so the
     sequential scan was fast enough to not trigger timeouts.
```

Root cause: process gap. The fix is not just adding the index -- it is also:
- Adding a query plan review step to the migration checklist
- Updating load tests to include high-ticket-count events
- Adding a slow query alert (queries > 500ms)

### The Incident Postmortem Preview

Your full incident timeline should look like this:

```
2:35 PM - Errors begin (detected later)
2:47 PM - Alert fires: purchase error rate > 5%
2:49 PM - Confirmed 8.3% error rate on /api/purchases only
2:51 PM - Found v2.8.1 deployed at 2:15 PM
2:54 PM - RED metrics: purchase-service slow + errors, event-service slow
2:57 PM - Logs: connection pool exhaustion + event-service timeouts
3:00 PM - Traces: availability query taking 4.7s (normally <50ms)
3:03 PM - Found: event DB nearly exhausted, Kafka consumer stuck
3:08 PM - Root causes identified (3 problems)
3:10 PM - Fix 1: Reset Kafka consumer past poison message
3:12 PM - Fix 2: Add missing database index (CONCURRENTLY)
3:15 PM - Connection pool recovering (cascade from fix 2)
3:20 PM - Error rate below 1%
3:30 PM - Error rate normal (< 0.1%), Kafka lag cleared
3:30 PM - Incident resolved
```

Total time: 43 minutes from alert to resolution. That is good. Most of that time was methodical diagnosis, not guessing.

---

## Part 5: Advanced Production Debugging Techniques

### Feature Flags for Debugging

Enable verbose logging for a specific user without redeploying:

```typescript
// If feature flags support user targeting:
if (featureFlags.isEnabled('debug_logging', { userId: req.user.id })) {
  req.log = req.log.child({ level: 'debug' });
}
```

This lets you get debug-level logs for a single user in production without flooding your log pipeline.

### Header-Based Debug Mode

```typescript
// Add a debug header that returns timing information
app.use((req, res, next) => {
  if (req.headers['x-debug'] === process.env.DEBUG_SECRET) {
    const start = process.hrtime.bigint();
    res.on('finish', () => {
      const duration = Number(process.hrtime.bigint() - start) / 1e6;
      console.log({
        level: 'debug',
        path: req.path,
        method: req.method,
        status: res.statusCode,
        durationMs: duration,
        dbQueries: req.queryCount,
        cacheHits: req.cacheHits,
      });
    });
  }
  next();
});
```

### Canary Debugging

If you suspect a fix will work but are not sure, deploy it to a small percentage of traffic:

```bash
# Using Kubernetes: run two versions simultaneously
kubectl -n ticketpulse set image deployment/purchase-service-canary \
  purchase-service=ticketpulse/purchase-service:v2.8.2-fix

# Route 5% of traffic to the canary
# (via service mesh or Ingress annotation)
```

Compare the canary's error rate against the stable version. If the canary's error rate drops, the fix works. Roll it out to 100%.

### The Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Better Approach |
|---|---|---|
| **Shotgun debugging** | Changing random things wastes time and introduces new variables | Follow the playbook: assess, check changes, check metrics, check logs, check traces |
| **Restarting first** | Destroys evidence (in-memory state, connection state, thread dumps) | Gather evidence first, then restart if needed |
| **Blaming the framework** | "It must be a Kubernetes bug" -- it almost never is | Check your code and configuration first |
| **Debugging alone for too long** | After 30 minutes without progress, you need fresh eyes | Escalate or pair-debug after 30 minutes of no progress |
| **Not writing things down** | You will forget what you already checked | Write the timeline as you go |
| **Fixing the symptom** | Increasing the timeout hides the slow query | Find and fix the root cause |

---

## 🤔 Reflect

Answer these questions in your engineering journal:

1. **In the scenario above, what was the first thing you would have checked?** Did your instinct match the systematic playbook?
2. **Why is the incident timeline important?** Who benefits from it?
3. **The 20-minute delay between deployment (2:15 PM) and errors (2:35 PM) -- what could cause that?** List three possibilities.
4. **How would you prevent Problem 1 from happening again?** Think about CI/CD, code review, monitoring, and testing.
5. **If you had to pick ONE observability tool for debugging, which would it be?** (Metrics, logs, or traces?) Why?

---

## Checkpoint

Before moving on, verify:

- [ ] You can follow the systematic debugging playbook (assess → changes → metrics → logs → traces → dependencies → isolate)
- [ ] You diagnosed all three problems using only observability tools
- [ ] You determined the correct fix order and can explain why
- [ ] You wrote an incident timeline documenting your investigation
- [ ] You applied the 5 Whys technique to reach the root cause
- [ ] You understand why the root cause is a process gap, not just a missing index
- [ ] You can explain three production debugging techniques (feature flags, header-based debug, canary debugging)

---

## Key Terms

| Term | Definition |
|------|-----------|
| **Observability** | The ability to understand a system's internal state by examining its external outputs (logs, metrics, traces). |
| **Incident** | An unplanned event that degrades or disrupts service, requiring immediate investigation and response. |
| **Root cause** | The fundamental reason a failure occurred, as opposed to its symptoms. |
| **5 Whys** | An iterative questioning technique that asks "why" repeatedly to drill down from a symptom to a root cause. |
| **Correlation** | The practice of linking related signals (logs, metrics, traces) to reconstruct the sequence of events in an incident. |
| **Triage** | The process of assessing severity and prioritizing which issues to investigate first during an incident. |

---

## What's Next

In **Technical Writing** (L2-M59), you'll sharpen the skill that multiplies your engineering impact — writing RFCs, docs, and incident reports that people actually read.

---

## Further Reading

- Chapter 18 of the 100x Engineer Guide (Debugging, Profiling & Monitoring) for language-specific debugging and profiling
- [Google SRE Book: Chapter 12 - Effective Troubleshooting](https://sre.google/sre-book/effective-troubleshooting/)
- [Charity Majors: "Observability Is Not Just Fancy Monitoring"](https://charity.wtf/)

> **Next up:** L2-M59 covers the documents every engineer writes -- RFCs, runbooks, and postmortems. You will write all three for TicketPulse.
