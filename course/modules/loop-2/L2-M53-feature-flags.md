# L2-M53: Feature Flags

> **Loop 2 (Practice)** | Section 2D: Advanced Patterns | ⏱️ 45 min | 🟢 Core | Prerequisites: L2-M39 (Kubernetes Basics)
>
> **Source:** Chapters 3, 22, 25, 32, 13 of the 100x Engineer Guide

---

## The Goal

TicketPulse wants to test a new "dynamic pricing" feature -- prices that change based on demand. The product team is not sure it will increase revenue. The engineering team is not sure it will not break something. Traditional deployment: build the feature, deploy to 100% of users, hope for the best. If it breaks, roll back the entire deployment.

Feature flags separate deployment from release. Deploy the code to 100% of servers. Enable the feature for 1% of users. Monitor. Increase to 10%. Monitor. If metrics look bad, disable the flag -- no deployment needed, no rollback, no downtime.

**You will run code within the first two minutes.**

---

## 0. Quick Start: The Simplest Flag (3 minutes)

```typescript
// src/flags/feature-flags.ts

import Redis from 'ioredis';

const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

interface FlagConfig {
  enabled: boolean;
  rolloutPercent: number;   // 0-100
  targetUserIds?: string[]; // Explicitly included users (for internal testing)
}

// Seed an initial flag
async function seedFlags() {
  await redis.hset('flags', 'dynamic_pricing', JSON.stringify({
    enabled: true,
    rolloutPercent: 10,
    targetUserIds: ['user_internal_1', 'user_internal_2'],
  }));
  console.log('[flags] Seeded dynamic_pricing flag at 10% rollout');
}

seedFlags();
```

```bash
# Verify the flag is in Redis
redis-cli hget flags dynamic_pricing | jq .
```

---

## 1. Build: Deterministic Flag Evaluation (10 minutes)

The critical requirement: **the same user must always see the same flag value**. If user A sees dynamic pricing on page load, they must see it on refresh, on a different device, and from a different server pod. No flickering.

```typescript
// src/flags/feature-flags.ts

import Redis from 'ioredis';
import crypto from 'crypto';

const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

interface FlagConfig {
  enabled: boolean;
  rolloutPercent: number;
  targetUserIds?: string[];
  createdAt?: string;
  description?: string;
  expiresAt?: string;    // Flag hygiene: when should this flag be cleaned up?
}

export async function isEnabled(flagName: string, userId: string): Promise<boolean> {
  const raw = await redis.hget('flags', flagName);
  if (!raw) return false;

  const config: FlagConfig = JSON.parse(raw);

  // Flag disabled globally
  if (!config.enabled) return false;

  // Explicit targeting: always include these users (for internal testing)
  if (config.targetUserIds?.includes(userId)) return true;

  // 100% rollout: everyone gets it
  if (config.rolloutPercent >= 100) return true;

  // 0% rollout: nobody gets it
  if (config.rolloutPercent <= 0) return false;

  // Deterministic bucketing: hash the user ID + flag name to get a stable number 0-99
  // Using the flag name in the hash means different flags give different buckets to the same user
  // (so user A is not always in the "first 10%" for every flag)
  const bucket = deterministicBucket(userId, flagName);
  return bucket < config.rolloutPercent;
}

function deterministicBucket(userId: string, flagName: string): number {
  const hash = crypto
    .createHash('sha256')
    .update(`${flagName}:${userId}`)
    .digest('hex');

  // Take the first 8 hex characters (32 bits) and mod by 100
  const value = parseInt(hash.substring(0, 8), 16);
  return value % 100;
}
```

**Why this works:**
- `sha256("dynamic_pricing:user_123")` always produces the same hash
- `parseInt(first8hex, 16) % 100` always produces the same number (0-99)
- If `rolloutPercent` is 10, users whose bucket is 0-9 get the feature
- When you increase to 20%, users 0-9 STILL get it (they are not re-bucketed), and users 10-19 are added
- No database state per user. No session cookies. Completely stateless.

Test it:

```typescript
// test/flag-bucketing.test.ts

import { deterministicBucket } from '../src/flags/feature-flags';

describe('deterministic bucketing', () => {
  it('same user + flag always produces the same bucket', () => {
    const bucket1 = deterministicBucket('user_123', 'dynamic_pricing');
    const bucket2 = deterministicBucket('user_123', 'dynamic_pricing');
    expect(bucket1).toBe(bucket2);
  });

  it('different flags produce different buckets for the same user', () => {
    const bucket1 = deterministicBucket('user_123', 'dynamic_pricing');
    const bucket2 = deterministicBucket('user_123', 'new_checkout_flow');
    // Not guaranteed to be different, but very likely with sha256
    // The point is they are independently distributed
  });

  it('roughly uniform distribution', () => {
    const buckets = new Map<number, number>();
    for (let i = 0; i < 10000; i++) {
      const b = deterministicBucket(`user_${i}`, 'test_flag');
      buckets.set(b, (buckets.get(b) || 0) + 1);
    }
    // Each bucket (0-99) should have roughly 100 users
    for (let b = 0; b < 100; b++) {
      const count = buckets.get(b) || 0;
      expect(count).toBeGreaterThan(50);
      expect(count).toBeLessThan(150);
    }
  });
});
```

---

## 2. Try It: Toggle and Observe (5 minutes)

Use the flag in the pricing logic:

```typescript
// src/services/pricing.service.ts (excerpt)

import { isEnabled } from '../flags/feature-flags';

async function calculateTicketPrice(
  eventId: string,
  tierName: string,
  userId: string
): Promise<number> {
  const basePrice = await getBasePrice(eventId, tierName);

  // Feature flag: dynamic pricing
  if (await isEnabled('dynamic_pricing', userId)) {
    const demand = await getDemandScore(eventId);
    const dynamicMultiplier = 1 + (demand * 0.5);  // Up to 50% increase at max demand
    console.log(`[pricing] Dynamic pricing for ${userId}: base=${basePrice}, multiplier=${dynamicMultiplier}`);
    return Math.round(basePrice * dynamicMultiplier);
  }

  return basePrice;
}
```

Test as different users:

```bash
# User in the 10% rollout (check by trying several user IDs)
curl http://localhost:3000/api/events/evt_1/price?userId=user_42
# Might return: { "price": 7500, "dynamic": true }

curl http://localhost:3000/api/events/evt_1/price?userId=user_99
# Might return: { "price": 5000, "dynamic": false }

# Explicitly targeted user always gets the feature
curl http://localhost:3000/api/events/evt_1/price?userId=user_internal_1
# Returns: { "price": 7500, "dynamic": true }
```

---

## 3. Build: Flag Admin API (8 minutes)

```typescript
// src/routes/admin/flags.routes.ts

import { Router, Request, Response } from 'express';
import Redis from 'ioredis';

const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
const router = Router();

// List all flags
router.get('/flags', async (req: Request, res: Response) => {
  const flags = await redis.hgetall('flags');
  const parsed = Object.fromEntries(
    Object.entries(flags).map(([name, config]) => [name, JSON.parse(config)])
  );
  res.json(parsed);
});

// Get a specific flag
router.get('/flags/:name', async (req: Request, res: Response) => {
  const raw = await redis.hget('flags', req.params.name);
  if (!raw) return res.status(404).json({ error: 'Flag not found' });
  res.json(JSON.parse(raw));
});

// Create or update a flag
router.put('/flags/:name', async (req: Request, res: Response) => {
  const { enabled, rolloutPercent, targetUserIds, description, expiresAt } = req.body;

  const existing = await redis.hget('flags', req.params.name);
  const current = existing ? JSON.parse(existing) : {};

  const updated = {
    ...current,
    enabled: enabled ?? current.enabled ?? false,
    rolloutPercent: rolloutPercent ?? current.rolloutPercent ?? 0,
    targetUserIds: targetUserIds ?? current.targetUserIds ?? [],
    description: description ?? current.description ?? '',
    expiresAt: expiresAt ?? current.expiresAt ?? null,
    createdAt: current.createdAt || new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };

  await redis.hset('flags', req.params.name, JSON.stringify(updated));

  console.log(`[flags] Updated ${req.params.name}: rollout=${updated.rolloutPercent}%, enabled=${updated.enabled}`);
  res.json(updated);
});

// Delete a flag
router.delete('/flags/:name', async (req: Request, res: Response) => {
  await redis.hdel('flags', req.params.name);
  res.status(204).send();
});

export default router;
```

Use it for a gradual rollout:

```bash
# Start at 1%
curl -X PUT http://localhost:3000/admin/flags/dynamic_pricing \
  -H 'Content-Type: application/json' \
  -d '{"enabled": true, "rolloutPercent": 1, "description": "Dynamic pricing based on demand"}'

# Monitor metrics for 1 hour...

# Increase to 10%
curl -X PUT http://localhost:3000/admin/flags/dynamic_pricing \
  -H 'Content-Type: application/json' \
  -d '{"rolloutPercent": 10}'

# Something looks wrong? Kill it instantly
curl -X PUT http://localhost:3000/admin/flags/dynamic_pricing \
  -H 'Content-Type: application/json' \
  -d '{"enabled": false}'
```

No deployment. No rollback. The change takes effect immediately because flag evaluation reads from Redis on every request.

---

## 4. Observe: Metrics by Variant (5 minutes)

Split metrics by flag variant to measure the feature's impact:

```typescript
// src/middleware/flag-metrics.ts

import { Counter, Histogram } from 'prom-client';

const purchasesByVariant = new Counter({
  name: 'purchases_total',
  help: 'Total purchases',
  labelNames: ['flag_dynamic_pricing'],
});

const revenueByVariant = new Counter({
  name: 'revenue_cents_total',
  help: 'Total revenue in cents',
  labelNames: ['flag_dynamic_pricing'],
});

const conversionByVariant = new Counter({
  name: 'checkout_started_total',
  help: 'Checkout flow started',
  labelNames: ['flag_dynamic_pricing'],
});

// In the purchase handler:
async function handlePurchase(userId: string, eventId: string, quantity: number) {
  const hasDynamicPricing = await isEnabled('dynamic_pricing', userId);
  const variant = hasDynamicPricing ? 'enabled' : 'disabled';

  conversionByVariant.inc({ flag_dynamic_pricing: variant });

  // ... process purchase ...

  purchasesByVariant.inc({ flag_dynamic_pricing: variant });
  revenueByVariant.inc({ flag_dynamic_pricing: variant }, totalCents);
}
```

Grafana dashboard:

```
Panel: Conversion Rate by Variant
  enabled:  rate(purchases_total{flag_dynamic_pricing="enabled"}[1h]) / rate(checkout_started_total{flag_dynamic_pricing="enabled"}[1h])
  disabled: rate(purchases_total{flag_dynamic_pricing="disabled"}[1h]) / rate(checkout_started_total{flag_dynamic_pricing="disabled"}[1h])

Panel: Revenue per User by Variant
  enabled:  rate(revenue_cents_total{flag_dynamic_pricing="enabled"}[1h]) / rate(purchases_total{flag_dynamic_pricing="enabled"}[1h])
  disabled: rate(revenue_cents_total{flag_dynamic_pricing="disabled"}[1h]) / rate(purchases_total{flag_dynamic_pricing="disabled"}[1h])
```

This is an A/B test built into the infrastructure. The flag splits traffic, the metrics measure the outcome.

---

## 5. Common Mistake: Flag Debt (3 minutes)

Feature flags accumulate. After six months, TicketPulse has 30 flags. Half of them are at 100% rollout and will never be turned off. The code is littered with `if (await isEnabled('feature_xyz', userId))` blocks where both branches are dead code. Nobody remembers what `checkout_v3_experiment` does.

This is flag debt. It is as real as technical debt.

---

## 6. Build: Flag Expiration Alerts (6 minutes)

```typescript
// src/flags/flag-hygiene.ts

import Redis from 'ioredis';

const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

interface StaleFlag {
  name: string;
  rolloutPercent: number;
  createdAt: string;
  ageInDays: number;
  reason: string;
}

export async function findStaleFlags(): Promise<StaleFlag[]> {
  const flags = await redis.hgetall('flags');
  const stale: StaleFlag[] = [];
  const now = new Date();

  for (const [name, raw] of Object.entries(flags)) {
    const config = JSON.parse(raw);
    if (!config.createdAt) continue;

    const createdAt = new Date(config.createdAt);
    const ageInDays = Math.floor((now.getTime() - createdAt.getTime()) / (1000 * 60 * 60 * 24));

    // Flag at 100% for more than 7 days -- should be removed and the code cleaned up
    if (config.rolloutPercent >= 100 && ageInDays > 7) {
      stale.push({
        name,
        rolloutPercent: config.rolloutPercent,
        createdAt: config.createdAt,
        ageInDays,
        reason: 'Fully rolled out for >7 days. Remove the flag and clean up the code.',
      });
    }

    // Flag at partial rollout for more than 30 days -- decision needed
    if (config.rolloutPercent > 0 && config.rolloutPercent < 100 && ageInDays > 30) {
      stale.push({
        name,
        rolloutPercent: config.rolloutPercent,
        createdAt: config.createdAt,
        ageInDays,
        reason: 'Partial rollout for >30 days. Either roll out to 100% or roll back.',
      });
    }

    // Flag that is past its explicit expiration date
    if (config.expiresAt && new Date(config.expiresAt) < now) {
      stale.push({
        name,
        rolloutPercent: config.rolloutPercent,
        createdAt: config.createdAt,
        ageInDays,
        reason: `Expired on ${config.expiresAt}. Clean up this flag.`,
      });
    }
  }

  return stale;
}

// Run as a scheduled job
async function main() {
  const stale = await findStaleFlags();
  if (stale.length === 0) {
    console.log('[flag-hygiene] All flags are clean.');
    return;
  }

  console.log(`[flag-hygiene] Found ${stale.length} stale flag(s):\n`);
  for (const flag of stale) {
    console.log(`  ${flag.name} (${flag.rolloutPercent}%, ${flag.ageInDays} days old)`);
    console.log(`  → ${flag.reason}\n`);
  }

  // In production: send this to Slack or create a Jira ticket
}

main().then(() => process.exit(0)).catch(console.error);
```

Schedule as a weekly cron job:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: flag-hygiene-check
spec:
  schedule: "0 9 * * 1"  # Every Monday at 9am
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: flag-hygiene
            image: ticketpulse/api:latest
            command: ["node", "dist/flags/flag-hygiene.js"]
          restartPolicy: OnFailure
```

---

## Checkpoint

Before continuing, verify:

- [ ] Feature flag evaluation is deterministic (same user always gets the same result)
- [ ] Rollout percentage works (10% means ~10% of users get the feature)
- [ ] Increasing the rollout percentage does not re-bucket existing users
- [ ] Admin API can create, update, and delete flags
- [ ] Metrics are split by flag variant
- [ ] Stale flag detection finds flags that need cleanup

```bash
git add -A && git commit -m "feat: add feature flag system with deterministic bucketing and hygiene checks"
```

---

## Reflect

Feature flags are one of the highest-leverage tools in software engineering. They decouple deployment from release, enable safe experimentation, and give product teams direct control over what users see. But they have a cost: every flag is a branch in the code that must eventually be resolved. The discipline to clean up flags is as important as the ability to create them.

The canonical example: Knight Capital lost $440 million in 45 minutes because old code was accidentally reactivated by a feature flag that was never cleaned up. Flag hygiene is not optional.

---

---

## 7. Extended Walkthrough: Gradual Rollout With Guardrails (20 min)

The dynamic pricing flag is live at 10%. Now simulate a real rollout decision process — the kind that happens in production every week.

### Step 1: Define Your Success Criteria Before Expanding

Before you touch the rollout percentage, write down what "success" means in concrete, measurable terms:

```markdown
# Dynamic Pricing Rollout Criteria

## Experiment Hypothesis
Enabling dynamic pricing for 10% of users will increase average revenue per ticket
by at least 8% without reducing conversion rate by more than 2%.

## Success Metrics (measured over the rollout window)
| Metric                        | Baseline (disabled) | Threshold (enabled must beat) |
|-------------------------------|---------------------|-------------------------------|
| Avg ticket price (cents)      | 5,000               | >= 5,400 (+8%)                |
| Checkout conversion rate      | 62%                 | >= 60.76% (no worse than -2%) |
| Purchase failure rate         | 0.3%                | <= 0.5%                       |
| p99 purchase latency (ms)     | 280ms               | <= 350ms                      |

## Rollout Schedule (if metrics pass)
Day 1-3:   10% rollout, monitor
Day 4-6:   25% rollout, monitor
Day 7-10:  50% rollout, monitor
Day 11-14: 75% rollout, monitor
Day 15:    100% rollout and schedule flag cleanup
```

Writing this BEFORE you look at the data prevents you from moving goalposts after the fact. This is how you make flag decisions defensible.

### Step 2: Query the Split Metrics

After 48 hours of 10% rollout, query Prometheus to compare variants:

```promql
# Conversion rate: enabled variant
rate(purchases_total{flag_dynamic_pricing="enabled"}[24h])
  /
rate(checkout_started_total{flag_dynamic_pricing="enabled"}[24h])

# Conversion rate: disabled variant (control)
rate(purchases_total{flag_dynamic_pricing="disabled"}[24h])
  /
rate(checkout_started_total{flag_dynamic_pricing="disabled"}[24h])
```

Run these Grafana queries and record:

```
Enabled  variant: conversion = __%, avg price = __¢, failure rate = __%
Disabled variant: conversion = __%, avg price = __¢, failure rate = __%
```

### Step 3: Make the Rollout Decision

Apply your success criteria:

```bash
# If enabled variant beats the threshold: expand the rollout
curl -X PUT http://localhost:3000/admin/flags/dynamic_pricing \
  -H 'Content-Type: application/json' \
  -d '{"rolloutPercent": 25}'

# If conversion rate dropped more than 2%: pause and investigate
curl -X PUT http://localhost:3000/admin/flags/dynamic_pricing \
  -H 'Content-Type: application/json' \
  -d '{"enabled": false}'

# Log the decision with reasoning
curl -X PUT http://localhost:3000/admin/flags/dynamic_pricing \
  -H 'Content-Type: application/json' \
  -d '{
    "rolloutPercent": 25,
    "description": "Day 4: Expanding to 25%. Conversion held at 61.8% (threshold: 60.76%). Avg price up 11.3% (threshold: +8%). Proceeding.",
    "updatedBy": "alice@ticketpulse.com"
  }'
```

### Step 4: Add an Automatic Kill Switch

Build an automated guard that disables the flag if metrics cross a threshold without human intervention:

```typescript
// src/flags/flag-guardian.ts

import { isEnabled } from './feature-flags';
import { queryPrometheus } from '../monitoring/prometheus-client';

interface GuardianConfig {
  flagName: string;
  // Prometheus query that returns a value (e.g., conversion rate)
  metric: string;
  // If metric drops below this, disable the flag
  threshold: number;
  // Evaluation window
  windowMinutes: number;
}

const GUARDIANS: GuardianConfig[] = [
  {
    flagName: 'dynamic_pricing',
    metric: `
      rate(purchases_total{flag_dynamic_pricing="enabled"}[30m])
      /
      rate(checkout_started_total{flag_dynamic_pricing="enabled"}[30m])
    `,
    threshold: 0.55,   // Kill if conversion drops below 55% (was 62%)
    windowMinutes: 30,
  },
];

export async function runFlagGuardians(): Promise<void> {
  for (const guardian of GUARDIANS) {
    const value = await queryPrometheus(guardian.metric);

    if (value !== null && value < guardian.threshold) {
      console.error(
        `[guardian] KILLING FLAG: ${guardian.flagName} — metric value ${value} is below threshold ${guardian.threshold}`
      );

      // Disable the flag
      await redis.hset('flags', guardian.flagName, JSON.stringify({
        ...(JSON.parse(await redis.hget('flags', guardian.flagName) || '{}')),
        enabled: false,
        disabledAt: new Date().toISOString(),
        disabledReason: `Auto-killed: metric ${value} < threshold ${guardian.threshold}`,
      }));

      // Alert the team
      await sendSlackAlert(
        `🚨 Feature flag '${guardian.flagName}' was automatically disabled.\n` +
        `Metric value: ${value} (threshold: ${guardian.threshold})\n` +
        `Check Grafana for details.`
      );
    }
  }
}

// Run every 5 minutes
setInterval(runFlagGuardians, 5 * 60 * 1000);
```

This is an automated circuit breaker for your feature rollout. If conversion rate collapses, the flag dies automatically — no engineer needs to be on call to disable it.

---

## 8. Real-World Pattern: Flags for Infrastructure Changes (10 min)

Feature flags are not just for product features. Use them for risky infrastructure migrations too.

### Example: Migrating from pg-pool to Prisma

You want to migrate TicketPulse's raw SQL queries in the event service to use Prisma. This is risky — Prisma generates different SQL, has different connection behavior, and might have subtle behavioral differences.

```typescript
// src/services/event.service.ts

import { isEnabled } from '../flags/feature-flags';

export async function getEvent(eventId: string, userId: string) {
  // Flag controls which data layer is used — not a product feature at all
  if (await isEnabled('event_service_prisma', userId)) {
    // New implementation: Prisma
    return prisma.event.findUnique({
      where: { id: eventId },
      include: { venue: true, organizer: true },
    });
  }

  // Old implementation: raw SQL
  const result = await db.query(`
    SELECT e.*, v.name AS venue_name, o.name AS organizer_name
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    JOIN organizers o ON e.organizer_id = o.id
    WHERE e.id = $1
  `, [eventId]);

  return result.rows[0];
}
```

Rollout strategy for infrastructure migrations:
1. Start at 1% (canary) — watch for query count differences, latency, error rates.
2. Compare `db_query_duration_ms` for old vs new implementation in your metrics.
3. If Prisma is producing the same results with comparable performance, expand.
4. If Prisma has a problem (N+1 regression, slow generated SQL), disable instantly with no user impact.
5. At 100%, schedule the flag cleanup and remove the old code path.

This pattern makes infrastructure migrations as safe as feature releases.

---

## 9. Reflect: The Knight Capital Lesson (5 min)

In 2012, Knight Capital lost $440 million in 45 minutes. A feature flag was the trigger.

Knight activated a dormant flag called `SMARS` to deploy a new order routing system on 7 out of 8 servers. The 8th server still had old code associated with that flag name — code that executed a "Power Peg" algorithm that was meant to have been deactivated years earlier. With the flag enabled, that server started buying and immediately selling millions of shares at market prices, creating massive losses.

The failure had multiple layers: old code that was never deleted, a flag name reused for a different purpose, no automated validation that all servers were running the same code version, and no kill switch to stop the runaway algorithm.

Reflect on these questions:

1. **How does your flag hygiene system prevent the "old code associated with a flag name" scenario?** What if you delete a flag and then reuse its name 6 months later for a different feature?

2. **If your `dynamic_pricing` flag was enabled on 7 of 8 pods — and the 8th pod had a different code path that crashed on flag evaluation — how would you detect this?** What monitoring would catch "flag enabled but pod health inconsistent"?

3. **Should feature flags have a mandatory description field? An owner?** What governance would you add to your flag system to prevent silent flag reuse?

> These are not rhetorical. Write your answers down. They will inform how you design flag systems at your next company.

---

> **Want the deep theory?** See Ch 22 of the 100x Engineer Guide: "Deployment Safety Patterns" — covers feature flags, canary releases, blue/green deployments, and progressive delivery with rollback strategies.

---

## Key Terms

| Term | Definition |
|------|-----------|
| **Feature flag** | A toggle that enables or disables a feature at runtime without deploying new code. |
| **Rollout** | The gradual process of enabling a feature for an increasing percentage of users. |
| **Canary** | A release strategy where a change is deployed to a small subset of users before a full rollout. |
| **A/B test** | An experiment that compares two variants of a feature to measure which performs better. |
| **Flag hygiene** | The practice of regularly cleaning up old or fully-rolled-out feature flags to reduce code complexity. |

## Further Reading

- Martin Fowler, "Feature Toggles" -- the comprehensive taxonomy of flag types (release, experiment, ops, permission)
- LaunchDarkly's architecture blog -- how a feature flag SaaS handles millions of evaluations per second
- "Accelerate" by Forsgren, Humble, Kim -- research showing that trunk-based development + feature flags correlates with elite engineering performance
