# L1-M26: SLOs & Error Budgets

> **Loop 1 (Foundation)** | Section 1E: Security & Reliability Basics | ⏱️ 60 min | 🟢 Core | Prerequisites: L1-M25 (Logging & Observability 101)
>
> **Source:** Chapters 5, 4, 20 of the 100x Engineer Guide

---

## The Goal

Ask any engineer: "Is TicketPulse reliable?" They will say "yes" or "mostly" or "it depends." None of those answers are useful because none of them are measurable.

Reliability is not a feeling. It is a number. This module teaches you how to define that number, measure it, and use it to make engineering decisions.

By the end, you will have concrete SLOs for TicketPulse, know how to calculate error budgets, and understand why "100% reliability" is the wrong goal.

> 💡 **Chapter 4 of the 100x Engineer Guide** covers the reliability philosophy behind SLOs — why Google invented this system, how it changed the industry, and the organizational dynamics that make it work. This module is the hands-on companion. You will define your first SLO within the first five minutes and build the measurement infrastructure to track it.

---

## 0. Quick Start: What Does "Reliable" Mean? (5 minutes)

Before we define anything formal, answer these questions for TicketPulse:

> **Reflect:** Write your answers down before reading further.
>
> 1. What is an acceptable error rate for TicketPulse? 1 in 100 requests fail? 1 in 1,000? 1 in 10,000?
> 2. How fast should the API respond? Is 500ms acceptable? What about 2 seconds?
> 3. If a user tries to buy a ticket, what percentage of attempts should succeed (assuming tickets are available)?
> 4. How many minutes of total downtime per month is acceptable?

There are no universally "correct" answers. The answers depend on your users, your business, and your engineering resources. But you need specific numbers, not vibes.

---

## 1. SLIs, SLOs, and SLAs: The Three Levels

| Term | What It Is | Who Defines It | Example |
|---|---|---|---|
| **SLI** (Service Level Indicator) | A measurement of service behavior | Engineering | "The proportion of requests that returned a non-5xx response" |
| **SLO** (Service Level Objective) | A target for an SLI | Engineering + Product | "99.9% of requests should return a non-5xx response" |
| **SLA** (Service Level Agreement) | A contract with consequences for missing it | Business + Legal | "If availability drops below 99.9%, customers get a 10% credit" |

The relationship: **SLIs are the measurements, SLOs are the targets, SLAs are the contracts.**

You always need SLIs (you cannot improve what you do not measure). You almost always need SLOs (targets focus engineering effort). You might need SLAs (if you have paying customers with contractual expectations).

---

## 2. Define TicketPulse SLOs

### 2.1 Availability SLO

**SLI:** The proportion of HTTP requests that return a non-5xx status code.

**SLO:** 99.9% of requests return a non-5xx response over a rolling 30-day window.

What does 99.9% mean in practice?

```
30 days = 43,200 minutes

99.9% availability = 0.1% error budget
0.1% of 43,200 = 43.2 minutes of allowed downtime per month

That's it. 43 minutes. Total. For the entire month.
```

For context:

| Target | Downtime per Month | Downtime per Year |
|---|---|---|
| 99% ("two nines") | 7.3 hours | 3.65 days |
| 99.9% ("three nines") | 43.2 minutes | 8.76 hours |
| 99.99% ("four nines") | 4.3 minutes | 52.6 minutes |
| 99.999% ("five nines") | 26 seconds | 5.26 minutes |

For a startup like TicketPulse, 99.9% is ambitious but achievable. 99.99% requires significant investment in redundancy and automation. 99.999% is Google/AWS territory and requires a fundamentally different approach to engineering.

### 2.2 Latency SLO

**SLI:** Request duration from the server's perspective (time between receiving the request and sending the response).

**SLO:**
- **p95:** 95% of requests complete in under 200ms
- **p99:** 99% of requests complete in under 1 second

Why two thresholds? Because averages lie. An average latency of 50ms can hide the fact that 1% of your users wait 10 seconds. The p99 tells you what the worst-case experience looks like for almost everyone.

```
If TicketPulse handles 100,000 requests per day:
- p95 at 200ms means 5,000 requests per day can exceed 200ms
- p99 at 1s means 1,000 requests per day can exceed 1 second
- The remaining 99,000 should be fast
```

### 2.3 Transaction Success SLO

**SLI:** The proportion of ticket purchase attempts that succeed (given tickets are available).

**SLO:** 99.95% of purchase attempts succeed.

This is a business-critical SLO. A failed purchase does not just annoy a user — it potentially loses revenue. We exclude cases where tickets are genuinely sold out (that is expected behavior, not an error).

```
99.95% success rate = 0.05% failure rate
If 10,000 people try to buy tickets today:
- 5 failures are within budget
- 6 failures means we've exceeded the SLO
```

---

## 3. Error Budget Math

### The Core Concept

The **error budget** is the inverse of your SLO. It is the amount of unreliability you are allowed.

```
SLO = 99.9%
Error budget = 100% - 99.9% = 0.1%
```

Over a 30-day window with 1,000,000 total requests:

```
Error budget = 0.1% of 1,000,000 = 1,000 errors allowed
```

If you have used 800 of your 1,000 error budget, you have 200 errors left for the rest of the month. This number drives real engineering decisions.

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Workshop: Error Budget Calculation

<details>
<summary>💡 Hint 1: Error budget = total requests times (1 minus SLO)</summary>
For a 99.9% SLO with 2.4 million requests: error budget = 2,400,000 x 0.001 = 2,400 allowed errors. If you have used 2,300, you have 100 remaining. That is 95.8% of your budget consumed — one bad deploy away from violating the SLO.
</details>

<details>
<summary>💡 Hint 2: Percentile SLOs work differently from availability SLOs</summary>
A p99 < 1s SLO means at most 1% of requests can exceed 1 second. With 10,000 requests, that is 100 allowed slow requests. If 1.5% exceeded 1s, that is 150 — you are 50 requests over budget. The SLO is violated even though 98.5% of requests were fine.
</details>

<details>
<summary>💡 Hint 3: Purchase success SLO — exclude expected failures</summary>
For the purchase success SLO (99.95%), only count failures due to system errors, not business logic (sold-out is expected). With 80,000 attempts and 85 payment timeouts: allowed = 80,000 x 0.0005 = 40. You are over by 45. This triggers a payment service investigation.
</details>


Work through these calculations yourself before reading the answers. Use a calculator.

**Problem 1:** TicketPulse has an availability SLO of 99.9%. In the last 30 days, the system handled 2.4 million requests and returned 2,300 errors.

- Error budget in requests: _____ (2.4M × 0.001)
- Errors used: 2,300
- Budget remaining: _____ requests
- Percentage of budget used: _____% 
- Are we within SLO? Yes / No

**Answer:** Budget = 2,400 errors. Used = 2,300. Remaining = 100 requests. Used = 95.8%. Still within SLO, but barely. One bad deploy would push us over.

**Problem 2:** TicketPulse has a latency SLO of p99 < 1 second. In the last hour, the system handled 10,000 requests. The slowest 1.5% of requests exceeded 1 second.

- Expected requests above threshold: _____ (1% of 10,000)
- Actual requests above threshold: _____ (1.5% of 10,000)
- Are we within the p99 SLO? Yes / No
- By how many requests are we over?

**Answer:** Expected = 100 requests above 1s. Actual = 150. Over by 50 requests. Violating the p99 SLO — 1.5% is above the 1% threshold.

**Problem 3:** TicketPulse has a purchase success SLO of 99.95%. During a flash sale for a Taylor Swift concert, 80,000 purchase attempts were made. 85 purchases failed due to a payment service timeout.

- Allowed failures: _____ (80,000 × 0.0005)
- Actual failures: 85
- Are we within SLO? Yes / No

**Answer:** Allowed = 40 failures. Actual = 85. Over by 45. SLO violated. This would trigger an immediate investigation of the payment service.

### 3.1 Error Budget as a Decision Framework

Here is how error budgets change the conversation:

**Scenario 1: Shipping a risky feature**

> PM: "We need to ship the new checkout flow this week."
> Engineer: "We've used 30 of our 43 minutes of downtime this month. The new flow has not been load tested."
> Decision: Run the load test first. If it passes, ship. If not, wait until next month when the error budget resets.

**Scenario 2: Performing maintenance**

> Engineer: "We need to upgrade PostgreSQL. It requires 5 minutes of downtime."
> SRE: "We have 40 minutes of budget remaining. 5 minutes is fine."
> Decision: Schedule the maintenance.

**Scenario 3: Error budget exhausted**

> Alert: "Error budget for availability exhausted (43/43 minutes used)."
> Action: Feature freeze. All engineering effort goes to reliability until the budget resets or the root causes are fixed.

> **Reflect:** "You've used 30 of your 43 minutes this month. A PM wants to ship a risky feature. What do you do?"
>
> The error budget gives you an objective answer. You are not saying "no" to the PM because you are cautious. You are saying "we have 13 minutes of reliability budget left, and this feature has not been tested under load. If it causes 14 minutes of degradation, we violate our SLO."

---

## 4. Measuring SLIs for TicketPulse

Defining SLOs is useless without measuring SLIs. Here is how we would measure each:

### 4.1 Availability SLI

```typescript
// src/middleware/sli-collector.ts

interface SLIMetrics {
  totalRequests: number;
  errorRequests: number;    // 5xx responses
  requestDurations: number[];
  purchaseAttempts: number;
  purchaseSuccesses: number;
  windowStart: Date;
}

const metrics: SLIMetrics = {
  totalRequests: 0,
  errorRequests: 0,
  requestDurations: [],
  purchaseAttempts: 0,
  purchaseSuccesses: 0,
  windowStart: new Date(),
};

export function sliCollector(req: Request, res: Response, next: NextFunction) {
  const start = Date.now();

  res.on('finish', () => {
    const durationMs = Date.now() - start;

    metrics.totalRequests++;
    metrics.requestDurations.push(durationMs);

    if (res.statusCode >= 500) {
      metrics.errorRequests++;
    }

    // Track purchase-specific metrics
    if (req.path.match(/\/api\/events\/\d+\/tickets/) && req.method === 'POST') {
      metrics.purchaseAttempts++;
      if (res.statusCode === 201) {
        metrics.purchaseSuccesses++;
      }
    }
  });

  next();
}

export function getSLIReport() {
  const availability = metrics.totalRequests > 0
    ? ((metrics.totalRequests - metrics.errorRequests) / metrics.totalRequests * 100).toFixed(4)
    : '100.0000';

  const sortedDurations = [...metrics.requestDurations].sort((a, b) => a - b);
  const p95Index = Math.floor(sortedDurations.length * 0.95);
  const p99Index = Math.floor(sortedDurations.length * 0.99);

  const purchaseSuccessRate = metrics.purchaseAttempts > 0
    ? ((metrics.purchaseSuccesses / metrics.purchaseAttempts) * 100).toFixed(4)
    : 'N/A';

  return {
    window: {
      start: metrics.windowStart.toISOString(),
      end: new Date().toISOString(),
      durationHours: ((Date.now() - metrics.windowStart.getTime()) / 3600000).toFixed(1),
    },
    availability: {
      slo: '99.9%',
      current: `${availability}%`,
      totalRequests: metrics.totalRequests,
      errorRequests: metrics.errorRequests,
      errorBudgetUsed: `${metrics.errorRequests} / ${Math.floor(metrics.totalRequests * 0.001)}`,
    },
    latency: {
      p95Slo: '200ms',
      p95Current: sortedDurations.length > 0 ? `${sortedDurations[p95Index]}ms` : 'N/A',
      p99Slo: '1000ms',
      p99Current: sortedDurations.length > 0 ? `${sortedDurations[p99Index]}ms` : 'N/A',
    },
    purchaseSuccess: {
      slo: '99.95%',
      current: `${purchaseSuccessRate}%`,
      attempts: metrics.purchaseAttempts,
      successes: metrics.purchaseSuccesses,
    },
  };
}
```

### 4.2 Expose the SLI Endpoint (Dev/Staging Only)

```typescript
// src/routes/metrics.ts

import { getSLIReport } from '../middleware/sli-collector';

router.get('/api/metrics/sli', (req, res) => {
  res.json(getSLIReport());
});
```

### 4.3 Try It

Generate some traffic and check the SLI report:

```bash
# Generate 100 requests
for i in $(seq 1 100); do
  curl -s http://localhost:3000/api/events > /dev/null
done

# Generate a few errors (request a non-existent endpoint)
for i in $(seq 1 3); do
  curl -s http://localhost:3000/api/nonexistent > /dev/null
done

# Check the SLI report
curl -s http://localhost:3000/api/metrics/sli | jq .
```

You should see something like:

```json
{
  "window": {
    "start": "2026-03-24T10:00:00.000Z",
    "end": "2026-03-24T10:15:00.000Z",
    "durationHours": "0.3"
  },
  "availability": {
    "slo": "99.9%",
    "current": "100.0000%",
    "totalRequests": 103,
    "errorRequests": 0,
    "errorBudgetUsed": "0 / 0"
  },
  "latency": {
    "p95Slo": "200ms",
    "p95Current": "45ms",
    "p99Slo": "1000ms",
    "p99Current": "120ms"
  },
  "purchaseSuccess": {
    "slo": "99.95%",
    "current": "N/A%",
    "attempts": 0,
    "successes": 0
  }
}
```

Note: The 404s from `/api/nonexistent` are not 5xx errors — they are client errors (4xx). They do not count against the availability SLO. This is intentional: a user requesting a URL that does not exist is not a service reliability issue.

### 4.4 The Dangerous Measurement Mistake: Server-Side Latency Only

There is a subtle bug in our SLI measurement: we are measuring latency from the server's perspective. But users experience latency from their browser's perspective. The difference is significant:

```
Server perspective:  request received → response sent = 45ms
User perspective:    link clicked → page rendered = 600ms

The gap includes:
  - Network round trip (user to server): 40ms
  - Server processing: 45ms
  - Network round trip (server to user): 40ms
  - Browser rendering: 475ms
  
Total user experience: 600ms
What we measure: 45ms
```

For an API-first product like TicketPulse, this matters less — but for page loads, always consider Real User Monitoring (RUM). Tools like Cloudflare Web Analytics, DataDog RUM, or Sentry Performance give you latency from the user's browser, not just the server.

**Quick fix for more accurate latency SLI:** measure from the load balancer or CDN, not the application server. ALB access logs include request/response timing that is closer to the user's reality.

---

## 5. SLO Workshop: Three Decision Scenarios

Work through these three scenarios. For each one, decide what you would do and explain why, using the error budget framework.

### Scenario A: The Risky Deploy

It is March 20th. Your 30-day rolling availability SLO is 99.9% (error budget: 43.2 minutes). So far this month you have used 30 minutes of your error budget due to a database migration that went sideways on March 8th.

A product manager wants to deploy a major checkout redesign. The feature has been tested in staging but has not been load tested. Historical data shows that major frontend changes cause 5-10 minutes of elevated error rates during the rollout.

**The math:**
- Budget remaining: 43.2 - 30 = 13.2 minutes
- Expected cost of deploy: 5-10 minutes
- Worst case: 10 minutes used, leaving 3.2 minutes for the rest of the month

**The decision:** This is tight but possible. The responsible approach: run a load test first (1 hour of effort). If it passes, deploy with a canary rollout (send 5% of traffic first, monitor for 10 minutes, then scale to 100%). If the canary shows elevated errors, roll back immediately. If you skip the load test and the deploy causes 15 minutes of errors, you have now violated your SLO.

**The negotiation:** Present the PM with options, not a flat "no":
- Option 1: Load test today, deploy Thursday with canary rollout (safest)
- Option 2: Deploy today with canary rollout, accept 2.2 minutes of buffer remaining
- Option 3: Wait until April 1st when the error budget resets

Option 1 is what you recommend. The error budget gives you the language to explain why.

### Scenario B: The Slow Burn

It is March 15th. Your latency SLO is p95 < 200ms. Looking at the metrics, p95 latency has been creeping up:
- March 1: p95 = 120ms
- March 5: p95 = 140ms
- March 10: p95 = 170ms
- March 15: p95 = 190ms

At this rate, you will breach the SLO by March 20th.

**The decision:** This is not an emergency yet, but it will be in 5 days. Open an investigation ticket. Common causes of gradual latency increase: growing database tables without index maintenance, cache hit rate declining, increased traffic without scaling.

**The right tools for slow burn detection:** Multi-window burn rate alerting (see Section 6) catches this. A single-point alert would not fire until March 20th. Burn rate alerting fires today, when there is still time to prevent the breach.

**Your investigation checklist:**
```bash
# Check database query performance over time
SELECT mean_exec_time, calls, query
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 20;

# Check cache hit rate
redis-cli INFO stats | grep keyspace_hits
redis-cli INFO stats | grep keyspace_misses

# Check if traffic has grown
# Query your analytics/APM tool for request rate trends
```

### Scenario C: The Business Pressure

It is the last day of the quarter. Sales has promised a major client that a specific feature will be available by end of day. The feature is ready but the test suite has 3 flaky tests that sometimes fail. The CI pipeline blocks deploys when tests fail.

The engineer suggests skipping the tests "just this once."

**The decision:** Never skip the tests. The flaky tests should have been fixed weeks ago — that is a separate failure. The correct action: fix the flaky tests (or temporarily skip those specific tests with a tracking ticket), run the full suite, deploy. If the flaky tests cannot be fixed in time, make the business case to the client for a one-day delay.

**The SLO lens:** If a deploy breaks the purchase flow for 20 minutes (which untested code has historically done), you have burned almost half your monthly error budget on a single preventable incident. The 24-hour delay costs less than the incident.

---

## 6. SLOs in the Real World

### 6.1 How Google Uses SLOs

Google's SRE book defines the SLO culture that now pervades the industry:

- **Every service has SLOs.** Not suggestions — requirements. You cannot launch a service without defined SLOs.
- **Error budgets are real.** When a team exhausts its error budget, feature work stops. All engineering effort shifts to reliability.
- **SLOs are negotiated.** Product and engineering agree on the targets together. Product wants high reliability (happy users). Engineering wants reasonable targets (ability to ship features).
- **SLOs are reviewed quarterly.** Too tight? Loosen them (you are over-investing in reliability). Too loose? Tighten them (users are complaining).

### 6.2 SLO Definition Workshop

Before you can measure SLOs, you need to define them carefully. Work through this for TicketPulse's three endpoints:

**Endpoint 1: `GET /api/events` (event listing)**

```
What good looks like:
  - Returns in < 200ms (p95) — browsing should feel instant
  - Returns a valid JSON array even if the database is slow (serve from cache)
  - Non-critical: a stale event listing is acceptable for 60 seconds

Proposed SLO:
  - Availability: 99.5% (lower than checkout — we can tolerate some browsing failures)
  - Latency p95: < 200ms
  - Latency p99: < 500ms
```

**Endpoint 2: `POST /api/tickets/purchase` (ticket purchase)**

```
What good looks like:
  - Returns success (201) or failure (409 sold out / 402 payment fail) quickly
  - Must never return a 500 — all errors should be handled gracefully
  - Revenue-critical: a failure here is a direct business loss

Proposed SLO:
  - Availability: 99.95% (higher — this is the money endpoint)
  - Latency p99: < 3s (payment processing adds latency)
  - Transaction success: 99.95% (given available inventory)
```

**Endpoint 3: `GET /api/users/me/orders` (order history)**

```
What good looks like:
  - Slight staleness is acceptable (30 seconds is fine)
  - Personalized — must always return data for the correct user
  - Nice to have: fast. Not critical.

Proposed SLO:
  - Availability: 99.0% (lower — this is a convenience feature)
  - Latency p95: < 500ms (slower is acceptable here)
```

### 6.3 Common SLO Mistakes

| Mistake | Why It Is Wrong | The Fix |
|---|---|---|
| Setting SLOs at 100% | Impossible and paralyzing | Set based on user expectations and business needs |
| Only measuring availability | Availability without latency is meaningless | Measure availability AND latency AND key transactions |
| Measuring from the server | Server thinks it responded in 50ms; the user waited 3s | Measure from the client or the load balancer |
| No one looks at the dashboard | SLOs without action are just numbers | Automate alerts on error budget burn rate |
| SLOs that never change | The product evolves; SLOs should too | Review quarterly |
| One SLO for all endpoints | The checkout page needs 99.99%; the about page needs 99% | Define per-service and per-endpoint SLOs |

---

## 7. Why Not 100%?

> **Insight:** Google's SRE book describes how YouTube intentionally serves slightly lower quality video during peak load to stay within error budgets. They accept slightly degraded quality to maintain overall availability.

100% reliability is the wrong target for three reasons:

1. **Diminishing returns.** Going from 99.9% to 99.99% costs 10x more in engineering effort, infrastructure, and complexity. Going from 99.99% to 99.999% costs 10x more again.

2. **Users cannot tell the difference.** If your API has 99.99% availability, a user would experience approximately 4 minutes of downtime per month. Their ISP, their WiFi, and their phone's network switching cause far more disruption than that.

3. **It kills velocity.** 100% reliability means zero risk. Zero risk means no deployments, no experiments, no features. The error budget is what gives you permission to innovate. If you have budget remaining, you can ship. If you do not, you fix reliability first.

The most reliable system is one that never changes. It is also the least useful.

---

## 8. SLO Burn Rate Alerts

Instead of alerting when the SLO is breached (too late), alert when you are burning through your error budget too fast:

```
Monthly error budget: 43.2 minutes

If you burn 43.2 minutes in 1 hour → something is catastrophically wrong (alert immediately)
If you burn 43.2 minutes in 6 hours → serious issue (alert urgently)
If you burn 43.2 minutes in 3 days → slow burn (alert in Slack, investigate during business hours)
```

This is called **multi-window burn rate alerting.** It gives you fast detection for severe incidents and slow detection for gradual degradation, without alerting on minor blips.

```
Fast burn (1h window):   error rate > 14.4x normal → page on-call
Slow burn (6h window):   error rate > 6x normal → urgent Slack alert
Gradual burn (3d window): error rate > 1x normal → ticket for investigation
```

### 🛠️ Build: Burn Rate Alert Implementation

<details>
<summary>💡 Hint 1: Burn rate = how fast you consume the monthly budget</summary>
Monthly budget is 43.2 minutes. If you burn that in 1 hour, you are consuming at 720x normal rate. The alert threshold of 14.4x catches it before the budget is fully exhausted (14.4x gives a 5x safety margin). The `rate()` function over a 1-hour window measures the error rate in that window.
</details>

<details>
<summary>💡 Hint 2: Use multi-window detection for different severity levels</summary>
Fast burn (1h window at 14.4x) is a critical page — something is catastrophically wrong. Slow burn (6h window at 6x) is a warning — investigate during business hours. Gradual burn (3d window at 1x) creates a ticket for investigation. Each window catches a different failure mode.
</details>

<details>
<summary>💡 Hint 3: The Prometheus expression divides error rate by total rate</summary>
The expression `sum(rate(http_requests_total{status=~"5.."}[1h])) / sum(rate(http_requests_total[1h]))` gives you the error fraction in the last hour. Compare it against `0.001 * 14.4` (the 14.4x burn rate threshold for a 99.9% SLO). Use `for: 2m` to avoid alerting on single-second spikes.
</details>


Here is how you would implement this in Prometheus/Alertmanager:

```yaml
# prometheus/alerts.yml

groups:
  - name: slo-availability
    rules:
      # Fast burn: consuming 43.2 minutes of budget in 1 hour
      # = 43.2x the normal error rate in a 1-hour window
      - alert: AvailabilitySLOFastBurn
        expr: |
          (
            sum(rate(http_requests_total{status=~"5.."}[1h]))
            /
            sum(rate(http_requests_total[1h]))
          ) > (0.001 * 14.4)
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Availability SLO fast burn detected"
          description: "Error rate is burning the monthly error budget at 14.4x the normal rate. At this pace, the monthly budget is exhausted in 1 hour."

      # Slow burn: consuming 43.2 minutes in 3 days
      - alert: AvailabilitySLOSlowBurn
        expr: |
          (
            sum(rate(http_requests_total{status=~"5.."}[6h]))
            /
            sum(rate(http_requests_total[6h]))
          ) > (0.001 * 6)
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Availability SLO slow burn detected"
          description: "Error rate is elevated. Investigate during business hours."
```

The burn rate multiplier math:
- Monthly budget: 43.2 minutes out of 43,200 minutes = 0.1% (0.001)
- If you burn the whole budget in 1 hour: you are erring at 43,200/60 = 720x normal. But we want to catch it before the budget is fully consumed — the 14.4x threshold gives a 5x safety margin (14.4 × 1 hour × 5 = 72 hours of budget burned in 1 hour → catch at 1/5 consumption).

---

## 9. Checkpoint

Before continuing to the next module, verify:

- [ ] You can define the three TicketPulse SLOs from memory (availability, latency, purchase success)
- [ ] You understand error budget math: 99.9% = 43.2 minutes/month of allowed downtime
- [ ] You completed the error budget calculation workshop (Problems 1-3) independently
- [ ] The SLI collector middleware is tracking requests, errors, and latency
- [ ] The `/api/metrics/sli` endpoint returns a real-time SLI report
- [ ] You can explain why 100% reliability is the wrong target
- [ ] You can use the error budget framework to make a shipping decision
- [ ] You understand the difference between fast burn and slow burn alerting

> **Reflect:** Think about a real product you use daily. What would you estimate its availability SLO is? If it went down for 5 minutes, would you notice? What about 5 hours? The gap between "5 minutes" and "I would notice" tells you where the real SLO probably sits.

---

## What's Next

TicketPulse now has security defenses, proper secrets management, structured logging, and defined SLOs. But when a new developer joins the team, they spend hours setting up their environment. The next module fixes the "works on my machine" problem with version managers, lockfiles, and automatic environment setup.

## Key Terms

| Term | Definition |
|------|-----------|
| **SLO** | Service Level Objective; a target value or range for a measurable aspect of service reliability. |
| **SLI** | Service Level Indicator; a quantitative measure of some aspect of the level of service being provided. |
| **SLA** | Service Level Agreement; a formal contract that specifies the consequences of not meeting SLOs. |
| **Error budget** | The allowed amount of unreliability derived from the SLO, balancing reliability work against feature development. |
| **Availability** | The proportion of time a service is operational and able to serve requests successfully. |
| **Uptime** | The total time a system remains accessible and functional within a given measurement period. |
| **Burn rate** | The rate at which the error budget is being consumed. A burn rate of 1x means the budget will be exhausted exactly at the end of the SLO window. |
| **Multi-window burn rate** | An alerting strategy that uses different time windows to catch both fast (catastrophic) and slow (gradual) budget consumption. |
| **p95 / p99** | Percentile latency measurements. p95 = 95% of requests are faster than this threshold. p99 = 99% of requests are faster. |

## Further Reading

- **Google SRE Book, Chapters 4 and 5**: Service Level Objectives — the original source of SLO methodology
- **Chapter 4 of the 100x Engineer Guide**: Reliability philosophy and the case for error budgets
- **"Alerting on SLOs like Pros"** (Slalom blog) — the burn rate alerting mathematics explained in detail
- **Alex Hidalgo, "Implementing Service Level Objectives"** — the book-length treatment of SLO practice
