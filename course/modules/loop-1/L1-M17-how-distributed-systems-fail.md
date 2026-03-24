# L1-M17: How Distributed Systems Fail

> **Loop 1 (Foundation)** | Section 1D: Architecture Fundamentals | Duration: 75 min | Tier: Core
>
> **Prerequisites:** L1-M10 (Caching Strategies), L1-M14 (First Deployment)
>
> **What you'll build:** Fault injection into TicketPulse — kill Redis, add Postgres latency, simulate network partitions — and implement fallback behavior so the application degrades gracefully instead of crashing.

---

## The Goal

TicketPulse depends on Postgres and Redis. Right now, if either goes down, the application crashes or hangs. That is unacceptable for a system that sells concert tickets. Users do not care why it broke. They care that they missed their chance to buy Taylor Swift tickets.

In this module, you will deliberately break things. You will kill Redis mid-request. You will add 5 seconds of latency to Postgres. You will watch TicketPulse fall apart. Then you will fix it so that it degrades gracefully instead of dying.

By the end, you will understand the CAP theorem not as abstract theory but as something you experienced with your own docker compose stack.

**You will break things within the first three minutes.**

---

## 0. Quick Start (3 minutes)

Make sure TicketPulse is running with both services:

```bash
cd ticketpulse
docker compose up -d postgres redis
npm run dev
```

Verify everything is healthy:

```bash
# Test the API
curl -s http://localhost:3000/api/events | jq '.data | length'
# Should return a number (your events)

# Test that caching is working (from M10)
curl -s http://localhost:3000/api/events > /dev/null
curl -s http://localhost:3000/api/events > /dev/null
docker exec ticketpulse-redis redis-cli INFO stats | grep keyspace_hits
# Should show hits > 0
```

Good. Everything works. Time to break it.

---

## 1. Break It: Kill Redis (10 minutes)

### The Experiment

TicketPulse uses Redis for caching event listings (from M10). What happens when Redis disappears?

```bash
# Stop Redis
docker compose stop redis
```

Now hit the API:

```bash
curl -s http://localhost:3000/api/events
```

### What Did You See?

One of three things happened, depending on how the Redis client is configured:

**Scenario A: The request hangs for 30+ seconds, then errors out.**
The Redis client is trying to connect, waiting for the default timeout. Every request is now blocked.

**Scenario B: The request crashes immediately with a connection error.**
The app returns a 500 Internal Server Error with a Redis connection refused stack trace.

**Scenario C: The request works, just slower.**
This is the best outcome, but TicketPulse almost certainly does not do this yet.

### 🔍 Try It: Measure the Impact

```bash
# Time the request with Redis down
time curl -s http://localhost:3000/api/events > /dev/null

# Compare: bring Redis back and time again
docker compose start redis
sleep 2
time curl -s http://localhost:3000/api/events > /dev/null
```

Note the difference. With Redis down, the request either hangs or crashes. With Redis up, it responds in milliseconds.

### 🤔 Reflect

Before we fix this, answer these questions:

1. Redis is a **cache**. It is not the source of truth. The data is in Postgres. If the cache is unavailable, should the application crash?
2. What would happen if TicketPulse was serving 1,000 users per second when Redis went down? How many users would see errors?
3. Is it better to return a slow response (skip cache, hit Postgres directly) or to return an error?

The answer to all of these: **a cache failure should never take down your application.** The cache makes things fast, but Postgres is the source of truth. If the cache is gone, serve from the database. It will be slower, but it will work.

---

## 2. Build: Redis Fallback Behavior (15 minutes)

### The Pattern: Try Cache, Fall Back to Database

```
Request comes in
  │
  ├── Try Redis
  │     │
  │     ├── Redis responds → return cached data (fast path)
  │     │
  │     ├── Redis is slow (>100ms) → abandon cache, query Postgres
  │     │
  │     └── Redis is down → query Postgres directly
  │
  └── Return data to client either way
```

### 🛠️ Build: Resilient Cache Wrapper

```typescript
// src/services/resilientCache.ts

import { createClient, RedisClientType } from 'redis';

export class ResilientCache {
  private client: RedisClientType;
  private isConnected: boolean = false;
  private reconnectTimer: NodeJS.Timeout | null = null;

  // Track cache health for monitoring
  private stats = {
    hits: 0,
    misses: 0,
    errors: 0,
    fallbacks: 0,
  };

  constructor(redisUrl: string) {
    this.client = createClient({ url: redisUrl });

    this.client.on('connect', () => {
      console.log('[cache] Redis connected');
      this.isConnected = true;
    });

    this.client.on('error', (err) => {
      console.warn('[cache] Redis error:', err.message);
      this.isConnected = false;
      this.scheduleReconnect();
    });

    this.client.on('end', () => {
      console.warn('[cache] Redis disconnected');
      this.isConnected = false;
    });
  }

  async connect(): Promise<void> {
    try {
      await this.client.connect();
    } catch (err) {
      console.warn('[cache] Initial connection failed, running without cache');
      this.isConnected = false;
    }
  }

  /**
   * Try to get from cache. If Redis is down or slow, return null (cache miss).
   * NEVER throw an error — the caller will fall back to Postgres.
   */
  async get(key: string): Promise<string | null> {
    if (!this.isConnected) {
      this.stats.fallbacks++;
      return null; // Skip cache entirely
    }

    try {
      const result = await Promise.race([
        this.client.get(key),
        this.timeout(100), // Abandon if Redis takes >100ms
      ]);

      if (result) {
        this.stats.hits++;
      } else {
        this.stats.misses++;
      }

      return result as string | null;
    } catch (err) {
      this.stats.errors++;
      console.warn(`[cache] GET ${key} failed:`, (err as Error).message);
      return null; // Fail open — treat as cache miss
    }
  }

  /**
   * Try to set in cache. If Redis is down, silently skip.
   * NEVER throw an error — the data is already in Postgres.
   */
  async set(key: string, value: string, ttlSeconds: number): Promise<void> {
    if (!this.isConnected) return;

    try {
      await this.client.set(key, value, { EX: ttlSeconds });
    } catch (err) {
      console.warn(`[cache] SET ${key} failed:`, (err as Error).message);
      // Silently fail — cache population is best-effort
    }
  }

  async del(key: string): Promise<void> {
    if (!this.isConnected) return;

    try {
      await this.client.del(key);
    } catch (err) {
      console.warn(`[cache] DEL ${key} failed:`, (err as Error).message);
    }
  }

  getStats() {
    return { ...this.stats };
  }

  private timeout(ms: number): Promise<never> {
    return new Promise((_, reject) =>
      setTimeout(() => reject(new Error(`Cache timeout after ${ms}ms`)), ms)
    );
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null;
      try {
        await this.client.connect();
      } catch {
        this.scheduleReconnect();
      }
    }, 5000); // Retry every 5 seconds
  }
}
```

### Key Design Decisions

Look at what this code does differently from a naive Redis wrapper:

1. **Never throws on cache operations.** `get()` returns `null` on failure. `set()` silently fails. The caller always gets a usable response.
2. **Timeout on reads.** If Redis is slow (degraded, not dead), we abandon the cache read after 100ms rather than blocking the user.
3. **Connection state tracking.** If we know Redis is down, we skip the attempt entirely — no wasted time.
4. **Automatic reconnection.** When Redis comes back, we reconnect without a restart.
5. **Metrics.** The `stats` object tracks hits, misses, errors, and fallbacks so we can monitor cache health.

### Update the Events Route

```typescript
// src/routes/events.ts (updated)

import { resilientCache } from '../services/resilientCache';

async function getEvents(req: Request, res: Response) {
  const cacheKey = 'events:listing';

  // Step 1: Try cache (will return null if Redis is down)
  const cached = await resilientCache.get(cacheKey);
  if (cached) {
    return res.json(JSON.parse(cached));
  }

  // Step 2: Cache miss or cache unavailable — query Postgres
  const events = await pool.query(`
    SELECT e.id, e.title, e.venue, e.date, e.available_tickets, e.price_in_cents
    FROM events e
    ORDER BY e.date
  `);

  const response = { data: events.rows };

  // Step 3: Try to populate cache (silently fails if Redis is down)
  await resilientCache.set(cacheKey, JSON.stringify(response), 300);

  return res.json(response);
}
```

### 🔍 Try It: Test the Fallback

```bash
# With Redis running — observe cache hits
curl -s http://localhost:3000/api/events > /dev/null
curl -s http://localhost:3000/api/events > /dev/null

# Kill Redis
docker compose stop redis

# Request still works! (falls back to Postgres)
time curl -s http://localhost:3000/api/events > /dev/null
# Should respond, just slower (no cache)

# Check the server logs
# You should see: [cache] Redis disconnected
# You should see: [cache] GET events:listing failed: ...

# Bring Redis back
docker compose start redis
sleep 3

# Cache should auto-reconnect
curl -s http://localhost:3000/api/events > /dev/null
curl -s http://localhost:3000/api/events > /dev/null
# Back to fast cached responses
```

This is **graceful degradation.** The system is slower without Redis, but it never crashes.

---

## 3. Break It: Slow Postgres (10 minutes)

Redis going down is one failure mode. But what about Postgres being slow — not dead, just painfully slow?

### Inject Latency

We will use `pg_sleep` to simulate a slow database:

```sql
-- In psql: create a function that wraps event queries with artificial delay
CREATE OR REPLACE FUNCTION slow_events() RETURNS SETOF events AS $$
BEGIN
  PERFORM pg_sleep(5); -- 5 second delay
  RETURN QUERY SELECT * FROM events;
END;
$$ LANGUAGE plpgsql;
```

A simpler way to simulate slow Postgres — use a network tool:

```bash
# Option 1: Use tc (traffic control) to add latency to the Postgres container
# This adds 3 seconds of latency to ALL network traffic to/from Postgres
docker exec ticketpulse-postgres apt-get update && apt-get install -y iproute2
docker exec ticketpulse-postgres tc qdisc add dev eth0 root netem delay 3000ms

# Now try a request (with Redis stopped so it hits Postgres)
docker compose stop redis
time curl -s http://localhost:3000/api/events > /dev/null
# Should take ~3+ seconds instead of milliseconds
```

If `tc` is not available, simulate it in application code:

```typescript
// TEMPORARY: Add to your events query for testing
async function getEventsFromDB() {
  // Simulate slow database (REMOVE THIS AFTER TESTING)
  await new Promise(resolve => setTimeout(resolve, 3000));
  return pool.query('SELECT * FROM events ORDER BY date');
}
```

### 🔍 Try It: What Slow Postgres Feels Like

```bash
# Terminal 1: Run 5 requests in parallel
for i in {1..5}; do
  time curl -s http://localhost:3000/api/events > /dev/null &
done
wait

# All 5 take ~3 seconds. With 1000 concurrent users, your connection pool
# is exhausted and new requests queue up. Response times go from 3s to 30s.
```

### The Problem: Slow Responses Cascade

When Postgres is slow:
1. Every request takes 3+ seconds instead of 50ms
2. Your connection pool fills up (default: 10-20 connections)
3. New requests wait for a free connection
4. Wait times compound: request #21 waits for one of the first 20 to finish
5. Timeouts start firing. Users see errors.
6. Load balancers mark the server as unhealthy.
7. The whole system falls over.

This is a **cascading failure.** One slow dependency takes down everything.

### Clean Up the Latency Injection

```bash
# Remove the simulated latency
docker exec ticketpulse-postgres tc qdisc del dev eth0 root 2>/dev/null

# Or if you used the setTimeout approach, remove it from code

# Restart Redis
docker compose start redis
```

---

## 4. The CAP Theorem — Through What You Just Experienced (10 minutes)

You just lived the CAP theorem. Let us name what happened.

### CAP: The Three Properties

**Consistency (C):** Every read gets the most recent write. If you buy a ticket, the next read shows that ticket as sold.

**Availability (A):** Every request gets a response (not an error). The system always answers.

**Partition Tolerance (P):** The system works even when network communication between components fails.

### The Theorem

In a distributed system, you can only guarantee two of three. Since network partitions always happen (you proved this by stopping Redis), you really choose between **CP** and **AP**.

### What You Experienced

**When you killed Redis (Section 1):**

Without the fallback, TicketPulse was neither consistent nor available — it just crashed. That is the worst outcome.

With the fallback (Section 2), TicketPulse chose **availability over the cache layer.** It served data from Postgres (consistent but slower). This is the right trade-off for a cache — caches are not the source of truth.

**When Postgres was slow (Section 3):**

The system was technically available (it responded... eventually). But a 3-second response is functionally the same as being down for users trying to buy tickets. PACELC captures this nuance.

### PACELC: The Rest of the Story

CAP only talks about partition events. But partitions are rare. Most of the time, the trade-off is:

> **P**artition → choose **A**vailability or **C**onsistency
> **E**lse (normal operation) → choose **L**atency or **C**onsistency

| Scenario | What TicketPulse Chose | Why |
|----------|----------------------|-----|
| Redis down (partition) | Availability (serve from Postgres) | Users can still browse events, just slower |
| Postgres slow (no partition) | Latency suffers | We accepted slow responses instead of returning stale data |
| Normal operation | Low latency via cache | Redis serves cached data in <1ms |

### The PACELC Classification of Systems You Know

| System | During Partition (PAC) | Normal Operation (ELC) |
|--------|----------------------|----------------------|
| TicketPulse (with fallback) | PA (available, eventual consistency) | EL (low latency via Redis cache) |
| Postgres (single node) | PC (refuses writes on partition) | EC (strong consistency) |
| Redis (single node cache) | Not applicable (it IS the partition) | EL (low latency, eventual via TTL) |
| DynamoDB | PA (always available) | EL (eventual consistency default) |
| MongoDB (majority writes) | PC (refuses minority-side writes) | EC (strong consistency) |

---

## 5. Build: Timeouts and Circuit Breakers (15 minutes)

The Postgres latency experiment revealed a critical weakness: TicketPulse waits forever for slow responses. We need timeouts.

### 🛠️ Build: Database Query Timeout

```typescript
// src/db/queryWithTimeout.ts

import { Pool, QueryResult } from 'pg';

const DEFAULT_TIMEOUT_MS = 5000; // 5 seconds

export async function queryWithTimeout(
  pool: Pool,
  sql: string,
  params: unknown[] = [],
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<QueryResult> {
  const client = await pool.connect();

  try {
    // Set a statement timeout for this specific query
    await client.query(`SET statement_timeout = ${timeoutMs}`);
    const result = await client.query(sql, params);
    return result;
  } catch (err) {
    const error = err as Error;
    if (error.message.includes('statement timeout')) {
      console.error(`[db] Query timed out after ${timeoutMs}ms: ${sql.substring(0, 100)}`);
      throw new Error(`Database query timed out after ${timeoutMs}ms`);
    }
    throw err;
  } finally {
    // Reset timeout and release connection
    await client.query('SET statement_timeout = 0').catch(() => {});
    client.release();
  }
}
```

### 🛠️ Build: Simple Circuit Breaker

A circuit breaker prevents your application from repeatedly calling a service that is known to be failing:

```typescript
// src/services/circuitBreaker.ts

type CircuitState = 'CLOSED' | 'OPEN' | 'HALF_OPEN';

export class CircuitBreaker {
  private state: CircuitState = 'CLOSED';
  private failureCount: number = 0;
  private lastFailureTime: number = 0;
  private successCount: number = 0;

  constructor(
    private readonly name: string,
    private readonly failureThreshold: number = 5,
    private readonly resetTimeoutMs: number = 30000, // 30 seconds
    private readonly halfOpenMaxAttempts: number = 3,
  ) {}

  async execute<T>(fn: () => Promise<T>, fallback: () => Promise<T>): Promise<T> {
    if (this.state === 'OPEN') {
      // Check if enough time has passed to try again
      if (Date.now() - this.lastFailureTime > this.resetTimeoutMs) {
        console.log(`[circuit:${this.name}] Transitioning to HALF_OPEN`);
        this.state = 'HALF_OPEN';
        this.successCount = 0;
      } else {
        console.log(`[circuit:${this.name}] OPEN — using fallback`);
        return fallback();
      }
    }

    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (err) {
      this.onFailure();
      console.warn(`[circuit:${this.name}] Call failed:`, (err as Error).message);
      return fallback();
    }
  }

  private onSuccess(): void {
    if (this.state === 'HALF_OPEN') {
      this.successCount++;
      if (this.successCount >= this.halfOpenMaxAttempts) {
        console.log(`[circuit:${this.name}] HALF_OPEN → CLOSED (recovered)`);
        this.state = 'CLOSED';
        this.failureCount = 0;
      }
    } else {
      this.failureCount = 0;
    }
  }

  private onFailure(): void {
    this.failureCount++;
    this.lastFailureTime = Date.now();

    if (this.state === 'HALF_OPEN') {
      console.log(`[circuit:${this.name}] HALF_OPEN → OPEN (still failing)`);
      this.state = 'OPEN';
    } else if (this.failureCount >= this.failureThreshold) {
      console.log(`[circuit:${this.name}] CLOSED → OPEN (${this.failureCount} failures)`);
      this.state = 'OPEN';
    }
  }

  getState(): CircuitState {
    return this.state;
  }
}
```

### Wire It Together

```typescript
// src/routes/events.ts (with circuit breaker)

import { CircuitBreaker } from '../services/circuitBreaker';
import { queryWithTimeout } from '../db/queryWithTimeout';

const dbCircuit = new CircuitBreaker('postgres', 5, 30000);

async function getEvents(req: Request, res: Response) {
  const cacheKey = 'events:listing';

  // Step 1: Try cache
  const cached = await resilientCache.get(cacheKey);
  if (cached) {
    return res.json(JSON.parse(cached));
  }

  // Step 2: Query Postgres with circuit breaker
  const result = await dbCircuit.execute(
    // Primary: query Postgres with timeout
    async () => {
      const events = await queryWithTimeout(
        pool,
        'SELECT id, title, venue, date, available_tickets, price_in_cents FROM events ORDER BY date',
        [],
        5000
      );
      return { data: events.rows, source: 'database' };
    },
    // Fallback: return a degraded response
    async () => {
      console.warn('[events] Postgres unavailable, returning degraded response');
      return {
        data: [],
        source: 'fallback',
        message: 'Event data temporarily unavailable. Please try again shortly.',
      };
    }
  );

  // Step 3: Cache if we got real data
  if (result.source === 'database') {
    await resilientCache.set(cacheKey, JSON.stringify(result), 300);
  }

  return res.json(result);
}
```

### 🔍 Try It: Circuit Breaker in Action

```bash
# Stop Postgres
docker compose stop postgres

# First 5 requests: circuit breaker counts failures
for i in {1..6}; do
  echo "Request $i:"
  curl -s http://localhost:3000/api/events | jq '.source // .message'
done

# After 5 failures, circuit OPENS
# Request 6+ should immediately return the fallback (no waiting)

# Watch the logs:
# [circuit:postgres] CLOSED → OPEN (5 failures)
# [circuit:postgres] OPEN — using fallback

# Restart Postgres
docker compose start postgres
sleep 3

# After 30 seconds, circuit goes HALF_OPEN
# Next requests probe Postgres — if it responds, circuit CLOSES
curl -s http://localhost:3000/api/events | jq '.source'
# Should eventually return "database" again
```

### The Circuit Breaker States

```
  CLOSED (normal)              OPEN (failing)           HALF_OPEN (testing)
  ┌──────────┐     5 failures  ┌──────────┐   timeout   ┌──────────┐
  │ Requests │ ───────────────→│ Requests │ ──────────→ │ Probe    │
  │ go to DB │                 │ go to    │             │ requests │
  │          │                 │ fallback │             │ try DB   │
  └──────────┘                 └──────────┘             └──────────┘
       ↑                                                    │ │
       │               3 consecutive successes              │ │
       └────────────────────────────────────────────────────┘ │
                                                              │
                           Any failure ──→ Back to OPEN ──────┘
```

---

## 6. Simulate a Network Partition (5 minutes)

A real network partition is when two components can talk to some things but not others. In a production system, this means one application server can reach Postgres but not Redis, while another can reach Redis but not Postgres.

We will simulate a simpler version:

```bash
# Disconnect Redis from the Docker network (it's running but unreachable)
docker network disconnect ticketpulse_default ticketpulse-redis

# TicketPulse can still reach Postgres but NOT Redis
curl -s http://localhost:3000/api/events | jq '.source'
# Should return "database" (Postgres direct, cache unavailable)

# Reconnect Redis
docker network connect ticketpulse_default ticketpulse-redis
sleep 2

# Cache should recover
curl -s http://localhost:3000/api/events > /dev/null
curl -s http://localhost:3000/api/events | jq '.source'
# Should return cached data again
```

This is a partition. Redis is running (it did not crash), but TicketPulse cannot reach it. The CAP theorem says this will happen. Your application must handle it.

---

## 7. Reflect: The TicketPulse Trade-Off (5 minutes)

### 🤔 The Big Question

TicketPulse sells concert tickets. Consider two failure scenarios:

**Scenario A: Consistency failure.** A user sees a ticket as "available" on the listing page, clicks "Buy," and gets told "sorry, that ticket was just sold." The listing was stale by 30 seconds.

**Scenario B: Availability failure.** The listing page is completely down. The user sees a 500 error. They cannot even browse events.

Which is worse for the business?

**For most ticket selling platforms, Scenario B is worse.** A user who sees "sorry, sold out" after clicking buy is mildly annoyed. A user who sees a 500 error leaves and never comes back. The stale listing is a minor inconvenience; the outage is lost revenue.

This is why Amazon chose availability for shopping carts (the Dynamo paper, 2007). A shopping cart that occasionally has a stale item is far better than a shopping cart that is down. You can always reconcile later — show the user an "item no longer available" message at checkout.

### 💡 Key Insight

The right trade-off depends on context:

| Operation | Choose | Why |
|-----------|--------|-----|
| Event listing page | Availability (AP) | Stale listings are acceptable. Outage is not. |
| Ticket purchase | Consistency (CP) | Must not oversell. A failed purchase is better than selling a phantom ticket. |
| User profile page | Availability (AP) | Showing a slightly stale profile is fine. |
| Payment processing | Consistency (CP) | Must be exactly-once. Money cannot be lost or doubled. |

**The trade-off is not system-wide. It is per-operation.** TicketPulse's listing page can be AP while the purchase endpoint is CP.

---

## 8. Checkpoint

After this module, TicketPulse should have:

- [ ] `ResilientCache` wrapper that never crashes on Redis failure
- [ ] Automatic fallback from cache to database when Redis is down
- [ ] `queryWithTimeout` that prevents Postgres queries from blocking forever
- [ ] A `CircuitBreaker` that stops hammering a failing dependency
- [ ] Experience injecting failures: `docker compose stop redis`, network disconnects, simulated latency
- [ ] Understanding of CAP theorem through concrete TicketPulse scenarios
- [ ] Understanding of PACELC: the latency vs. consistency trade-off during normal operation

**Your TicketPulse should survive `docker compose stop redis` without crashing.**

---

## Glossary

| Term | Definition |
|------|-----------|
| **CAP theorem** | In a distributed system, you can guarantee at most two of: Consistency, Availability, Partition Tolerance. Since partitions happen, you choose CP or AP. |
| **PACELC** | Extension of CAP: during Partition choose A or C; Else (normal) choose Latency or Consistency. Captures the everyday trade-off. |
| **Network partition** | When two components cannot communicate even though both are running. The network between them is broken. |
| **Graceful degradation** | When a dependency fails, the system continues operating with reduced functionality instead of crashing. |
| **Circuit breaker** | A pattern that stops calling a failing service after N failures. Prevents cascading failures. States: Closed, Open, Half-Open. |
| **Cascading failure** | When one slow or failing component causes other components to fail, spreading through the system like dominoes. |
| **Fail open** | When a component fails, allow the operation (possibly with reduced functionality). Cache failures should fail open. |
| **Fail closed** | When a component fails, deny the operation. Security checks should fail closed. |
| **Timeout** | A deadline for an operation. If the operation does not complete within the deadline, it is cancelled. Every network call must have one. |
| **Fallback** | An alternative behavior when the primary path fails. Serving from Postgres when Redis is down is a fallback. |

---

## Further Reading

- [The Dynamo Paper (Amazon, 2007)](https://www.allthingsdistributed.com/2007/10/amazons_dynamo.html) — The paper that shaped modern distributed systems thinking
- [CAP Twelve Years Later](https://www.infoq.com/articles/cap-twelve-years-later-how-the-rules-have-changed/) — Eric Brewer's own retrospective on CAP
- Martin Kleppmann, *Designing Data-Intensive Applications*, Chapter 8 (The Trouble with Distributed Systems)
- Chapter 1 of the 100x Engineer Guide: Sections 1.1-1.2 (CAP and PACELC)
