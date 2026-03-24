# L1-M26: SLOs & Error Budgets

> **Loop 1 (Foundation)** | Section 1E: Security & Reliability Basics | ⏱️ 45 min | 🟢 Core | Prerequisites: L1-M25 (Logging & Observability 101)
>
> **Source:** Chapters 5, 4, 20 of the 100x Engineer Guide

---

## The Goal

Ask any engineer: "Is TicketPulse reliable?" They will say "yes" or "mostly" or "it depends." None of those answers are useful because none of them are measurable.

Reliability is not a feeling. It is a number. This module teaches you how to define that number, measure it, and use it to make engineering decisions.

By the end, you will have concrete SLOs for TicketPulse, know how to calculate error budgets, and understand why "100% reliability" is the wrong goal.

**You will define your first SLO within the first five minutes.**

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

This is a business-critical SLO. A failed purchase does not just annoy a user -- it potentially loses revenue. We exclude cases where tickets are genuinely sold out (that is expected behavior, not an error).

```
99.95% success rate = 0.05% failure rate
If 10,000 people try to buy tickets today:
- 5 failures are within budget
- 6 failures means we've exceeded the SLO
```

---

## 3. Error Budget Math

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

Note: The 404s from `/api/nonexistent` are not 5xx errors -- they are client errors (4xx). They do not count against the availability SLO. This is intentional: a user requesting a URL that does not exist is not a service reliability issue.

---

## 5. Exercise: SLO-Based Decision Making

Work through these three scenarios. For each one, decide what you would do and explain why, using the error budget framework.

### Scenario A: The Risky Deploy

It is March 20th. Your 30-day rolling availability SLO is 99.9% (error budget: 43.2 minutes). So far this month you have used 30 minutes of your error budget due to a database migration that went sideways on March 8th.

A product manager wants to deploy a major checkout redesign. The feature has been tested in staging but has not been load tested. Historical data shows that major frontend changes cause 5-10 minutes of elevated error rates during the rollout.

**The math:**
- Budget remaining: 43.2 - 30 = 13.2 minutes
- Expected cost of deploy: 5-10 minutes
- Worst case: 10 minutes used, leaving 3.2 minutes for the rest of the month

**The decision:** This is tight but possible. The responsible approach: run a load test first (1 hour of effort). If it passes, deploy with a canary rollout (send 5% of traffic first, monitor for 10 minutes, then scale to 100%). If the canary shows elevated errors, roll back immediately. If you skip the load test and the deploy causes 15 minutes of errors, you have now violated your SLO.

### Scenario B: The Slow Burn

It is March 15th. Your latency SLO is p95 < 200ms. Looking at the metrics, p95 latency has been creeping up:
- March 1: p95 = 120ms
- March 5: p95 = 140ms
- March 10: p95 = 170ms
- March 15: p95 = 190ms

At this rate, you will breach the SLO by March 20th.

**The decision:** This is not an emergency yet, but it will be in 5 days. Open an investigation ticket. Common causes of gradual latency increase: growing database tables without index maintenance, cache hit rate declining, increased traffic without scaling. This is exactly what "gradual burn" alerting catches -- the slow degradation that does not trigger incident alerts but will breach the SLO if left unchecked.

### Scenario C: The Business Pressure

It is the last day of the quarter. Sales has promised a major client that a specific feature will be available by end of day. The feature is ready but the test suite has 3 flaky tests that sometimes fail. The CI pipeline blocks deploys when tests fail.

The engineer suggests skipping the tests "just this once."

**The decision:** Never skip the tests. The flaky tests should have been fixed weeks ago -- that is a separate failure. The correct action: fix the flaky tests (or temporarily skip those specific tests with a tracking ticket), run the full suite, deploy. If the flaky tests cannot be fixed in time, make the business case to the client for a one-day delay. A production incident caused by an untested deploy will cost more than a one-day delay.

---

## 6. SLOs in the Real World

### 6.1 How Google Uses SLOs

Google's SRE book defines the SLO culture that now pervades the industry:

- **Every service has SLOs.** Not suggestions -- requirements. You cannot launch a service without defined SLOs.
- **Error budgets are real.** When a team exhausts its error budget, feature work stops. All engineering effort shifts to reliability.
- **SLOs are negotiated.** Product and engineering agree on the targets together. Product wants high reliability (happy users). Engineering wants reasonable targets (ability to ship features).
- **SLOs are reviewed quarterly.** Too tight? Loosen them (you are over-investing in reliability). Too loose? Tighten them (users are complaining).

### 6.2 Common SLO Mistakes

| Mistake | Why It Is Wrong | The Fix |
|---|---|---|
| Setting SLOs at 100% | Impossible and paralyzing | Set based on user expectations and business needs |
| Only measuring availability | Availability without latency is meaningless | Measure availability AND latency AND key transactions |
| Measuring from the server | Server thinks it responded in 50ms; the user waited 3s | Measure from the client or the load balancer |
| No one looks at the dashboard | SLOs without action are just numbers | Automate alerts on error budget burn rate |
| SLOs that never change | The product evolves; SLOs should too | Review quarterly |

---

## 7. Why Not 100%?

> **Insight:** Google's SRE book describes how YouTube intentionally serves slightly lower quality video during peak load to stay within error budgets. They accept slightly degraded quality to maintain overall availability.

100% reliability is the wrong target for three reasons:

1. **Diminishing returns.** Going from 99.9% to 99.99% costs 10x more in engineering effort, infrastructure, and complexity. Going from 99.99% to 99.999% costs 10x more again.

2. **Users cannot tell the difference.** If your API has 99.99% availability, a user would experience approximately 4 minutes of downtime per month. Their ISP, their WiFi, and their phone's network switching cause far more disruption than that.

3. **It kills velocity.** 100% reliability means zero risk. Zero risk means no deployments, no experiments, no features. The error budget is what gives you permission to innovate. If you have budget remaining, you can ship. If you do not, you fix reliability first.

The most reliable system is one that never changes. It is also the least useful.

---

## 6. SLO Burn Rate Alerts

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

---

## 7. Checkpoint

Before continuing to the next module, verify:

- [ ] You can define the three TicketPulse SLOs from memory (availability, latency, purchase success)
- [ ] You understand error budget math: 99.9% = 43.2 minutes/month of allowed downtime
- [ ] The SLI collector middleware is tracking requests, errors, and latency
- [ ] The `/api/metrics/sli` endpoint returns a real-time SLI report
- [ ] You can explain why 100% reliability is the wrong target
- [ ] You can use the error budget framework to make a shipping decision

> **Reflect:** Think about a real product you use daily. What would you estimate its availability SLO is? If it went down for 5 minutes, would you notice? What about 5 hours? The gap between "5 minutes" and "I would notice" tells you where the real SLO probably sits.

---

## What's Next

TicketPulse now has security defenses, proper secrets management, structured logging, and defined SLOs. But when a new developer joins the team, they spend hours setting up their environment. The next module fixes the "works on my machine" problem with version managers, lockfiles, and automatic environment setup.
