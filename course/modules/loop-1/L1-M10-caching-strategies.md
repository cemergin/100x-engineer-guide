# L1-M10: Caching Strategies

> **Loop 1 (Foundation)** | Section 1B: Data & Databases | ⏱️ 60 min | 🟢 Core | Prerequisites: L1-M05, L1-M09
>
> **Source:** Chapters 2, 24 of the 100x Engineer Guide

## What You'll Learn
- Why caching matters and the cache-aside pattern
- How to implement cache-aside for a real API endpoint
- TTL strategy: how long to cache different types of data
- Cache invalidation: what happens when the source data changes
- Write-through, write-behind, and cache-aside compared
- How to observe cache hit ratios and diagnose cache problems
- The stale data nightmare and how to prevent it

## Why This Matters
Without caching, every request to TicketPulse's event listing page fires a SQL query with multiple JOINs. At 10 requests per second, that's fine. At 1,000 requests per second, your database melts. Caching lets you serve the same data to hundreds of users from Redis in sub-millisecond time, hitting Postgres only when the cache is empty or stale. Caching is the single highest-impact performance optimization for most web applications.

## Prereq Check

You need both Postgres and Redis running from previous modules:

```bash
docker ps | grep -E 'postgres|redis'
# Should show both containers running
```

Connect to both:

```bash
# Terminal 1: Postgres
docker exec -it ticketpulse-postgres psql -U ticketpulse

# Terminal 2: Redis
docker exec -it ticketpulse-redis redis-cli
```

---

## Part 1: The Problem (5 min)

### 🔍 Try It Now

In your Postgres terminal, run the event listing query that would power the TicketPulse homepage:

```sql
\timing on

SELECT e.id, e.name AS event_name,
       v.name AS venue_name, v.city,
       e.event_date, e.status,
       COUNT(t.id) AS total_tickets,
       COUNT(t.id) FILTER (WHERE t.status = 'available') AS available,
       MIN(t.price) FILTER (WHERE t.status = 'available') AS min_price
FROM events e
JOIN venues v ON e.venue_id = v.id
LEFT JOIN tickets t ON t.event_id = e.id
GROUP BY e.id, e.name, v.name, v.city, e.event_date, e.status
ORDER BY e.event_date;
```

Note the execution time. Now imagine this running 1,000 times per second.

The math:
- If this query takes 50ms: 1,000 * 50ms = **50 seconds of database time per second**
- That's 50 CPU-seconds of Postgres work every second — for a single endpoint
- Your database can handle maybe 100 concurrent queries before response times spike

**Every one of those 1,000 requests returns the same data.** Events don't change every millisecond. This is the perfect case for caching.

---

## Part 2: Cache-Aside Pattern (15 min)

Cache-aside (also called "lazy loading") is the most common caching pattern. The application manages the cache explicitly:

```
Request comes in
  │
  ├── Check Redis: "Do I have this data cached?"
  │     │
  │     ├── YES (cache hit) → Return cached data. Done.
  │     │
  │     └── NO (cache miss) → Query Postgres
  │                              │
  │                              ├── Store result in Redis with TTL
  │                              └── Return data to client
```

### 🛠️ Build: Cache-Aside for GET /api/events

Here's the implementation in pseudocode that maps to any language:

```
FUNCTION get_events():
    cache_key = "events:listing"

    # Step 1: Check cache
    cached = redis.GET(cache_key)
    if cached is not null:
        log("cache HIT")
        return JSON.parse(cached)

    # Step 2: Cache miss — query database
    log("cache MISS — querying Postgres")
    events = postgres.query("""
        SELECT e.id, e.name AS event_name,
               v.name AS venue_name, v.city,
               e.event_date, e.status,
               COUNT(t.id) FILTER (WHERE t.status = 'available') AS available,
               MIN(t.price) FILTER (WHERE t.status = 'available') AS min_price
        FROM events e
        JOIN venues v ON e.venue_id = v.id
        LEFT JOIN tickets t ON t.event_id = e.id
        GROUP BY e.id, e.name, v.name, v.city, e.event_date, e.status
        ORDER BY e.event_date
    """)

    # Step 3: Store in cache with 5-minute TTL
    redis.SET(cache_key, JSON.stringify(events), EX=300)

    return events
```

### 🔍 Try It Now: Simulate Cache-Aside Manually

Let's do this by hand across your two terminals.

**Terminal 2 (Redis) — Check cache:**

```redis
GET events:listing
-- Returns: (nil) — cache miss!
```

**Terminal 1 (Postgres) — Query the database:**

```sql
SELECT json_agg(event_data) FROM (
    SELECT e.id, e.name AS event_name,
           v.name AS venue_name, v.city,
           e.event_date::text, e.status,
           COUNT(t.id) FILTER (WHERE t.status = 'available') AS available,
           MIN(t.price) FILTER (WHERE t.status = 'available') AS min_price
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    LEFT JOIN tickets t ON t.event_id = e.id
    GROUP BY e.id, e.name, v.name, v.city, e.event_date, e.status
    ORDER BY e.event_date
) event_data;
```

Copy the JSON output (it will be a large JSON array).

**Terminal 2 (Redis) — Store in cache:**

```redis
SET events:listing '[{"id":1,"event_name":"Aurora Flux: Synthesis Tour","venue_name":"Madison Square Garden","city":"New York","event_date":"2026-06-15","status":"on_sale","available":5,"min_price":45.00}]' EX 300
```

(Use the actual JSON from your query — the above is a simplified example.)

**Terminal 2 (Redis) — Verify cache hit:**

```redis
GET events:listing
-- Returns: the JSON string — cache HIT!

TTL events:listing
-- Returns: ~298 (seconds remaining)
```

Now for the next 5 minutes, every request reads from Redis (sub-millisecond) instead of hitting Postgres (50ms+).

---

## Part 3: TTL Strategy (10 min)

TTL (Time To Live) determines how long cached data is valid. Too short = cache is useless (constant misses). Too long = users see stale data.

### TTL Guidelines for TicketPulse

| Data | TTL | Reasoning |
|------|-----|-----------|
| Event listing (homepage) | 5 min | Events change infrequently. 5-minute staleness is acceptable. |
| Single event details | 2 min | Users might check availability before buying. Fresher is better. |
| Ticket availability count | 30 sec | Changes with every purchase. Needs to be fairly current. |
| Venue information | 1 hour | Almost never changes. |
| Artist profiles | 1 hour | Almost never changes. |
| Search results | 1 min | Depends on query. Short TTL for varied queries. |
| User session | 1 hour | Extended on each request (sliding window). |

### 🔍 Try It Now: Different TTLs

```redis
-- Long TTL for static data
SET venue:1 '{"name":"Madison Square Garden","city":"New York"}' EX 3600

-- Medium TTL for semi-dynamic data
SET events:listing '[...]' EX 300

-- Short TTL for fast-changing data
SET event:1:availability '{"available":42}' EX 30

-- Check them all
TTL venue:1
TTL events:listing
TTL event:1:availability
```

### 🤔 Reflect: The TTL Trade-off

Shorter TTL means:
- Fresher data (good for user experience)
- More cache misses (more Postgres queries)
- Higher database load

Longer TTL means:
- More cache hits (less database load)
- Staler data (users might see outdated info)
- Risk of selling "available" tickets that are already sold

For TicketPulse, the critical question is: **what happens if a user sees a ticket as "available" but it was sold 30 seconds ago?** They click buy, and the application checks Postgres at purchase time and returns "sorry, this ticket is no longer available." That's acceptable. A 30-second staleness for the listing is fine because the purchase itself always hits the source of truth (Postgres).

---

## Part 4: Cache Invalidation (10 min)

> "There are only two hard things in Computer Science: cache invalidation and naming things." — Phil Karlton

Cache invalidation means removing or updating cached data when the source data changes.

### Strategy 1: TTL-Based Expiration (Simplest)

Just let the cache expire naturally. After the TTL, the next request triggers a cache miss, queries Postgres, and repopulates the cache.

```redis
-- Data goes stale after TTL, then auto-refreshes on next request
SET events:listing '[...]' EX 300
-- After 300 seconds: key disappears, next request refills it
```

**Pros:** Dead simple. No coordination needed.
**Cons:** Data can be stale for up to TTL duration.

### Strategy 2: Explicit Invalidation (On Write)

When data changes, immediately delete the cache:

```
FUNCTION update_event(event_id, data):
    # Update the database
    postgres.query("UPDATE events SET ... WHERE id = ?", event_id)

    # Invalidate related caches
    redis.DEL("events:listing")
    redis.DEL("event:{event_id}")
    redis.DEL("event:{event_id}:availability")
```

### 🔍 Try It Now: Simulate Cache Invalidation

**Terminal 2 (Redis) — Verify cache exists:**

```redis
GET events:listing
-- Returns: cached data

-- Simulate an event update (admin changes event details)
DEL events:listing
DEL event:1

-- Verify invalidation
GET events:listing
-- Returns: (nil) — next request will query Postgres
```

### 🐛 Debug: The Stale Data Problem

Let's intentionally create a cache inconsistency and see what happens.

**Terminal 2 (Redis) — Cache the current data:**

```redis
SET event:1:name "Aurora Flux: Synthesis Tour" EX 600
GET event:1:name
-- Returns: "Aurora Flux: Synthesis Tour"
```

**Terminal 1 (Postgres) — Update the event:**

```sql
UPDATE events SET name = 'Aurora Flux: FINAL Synthesis Tour' WHERE id = 1;
SELECT name FROM events WHERE id = 1;
-- Returns: "Aurora Flux: FINAL Synthesis Tour"
```

**Terminal 2 (Redis) — Check the cache:**

```redis
GET event:1:name
-- Returns: "Aurora Flux: Synthesis Tour" — STALE! The old name!
```

The database says "FINAL Synthesis Tour" but the cache says "Synthesis Tour." A user sees the old name for up to 10 minutes (our 600s TTL).

**Fix it:**

```redis
-- Option 1: Delete the cache (cache-aside invalidation)
DEL event:1:name
-- Next read will fetch from Postgres and get the correct name

-- Option 2: Update the cache directly (write-through)
SET event:1:name "Aurora Flux: FINAL Synthesis Tour" EX 600
```

### ⚠️ Common Mistake: Caching Without TTL

```redis
-- NEVER do this in production:
SET events:listing '[...]'
-- No EX! This data lives in Redis FOREVER.
-- If the application crashes before invalidating, you have permanent stale data.

-- ALWAYS set a TTL, even if you also do explicit invalidation:
SET events:listing '[...]' EX 300
-- TTL is your safety net. Even if invalidation fails, data refreshes in 5 minutes.
```

---

## Part 5: Caching Patterns Compared (5 min)

### Cache-Aside (What We Built)

```
Read:  App → Redis (miss?) → Postgres → Redis → App
Write: App → Postgres → (optionally) DEL from Redis
```

- **Most common.** Application controls everything.
- Good for general purpose. Simple to implement.
- Risk: cache miss thundering herd (many requests miss simultaneously).

### Write-Through

```
Read:  App → Redis (always populated)
Write: App → Redis AND Postgres (synchronously)
```

- Cache is always warm and consistent.
- Higher write latency (must write to both).
- Good when read-after-write consistency is critical.

### Write-Behind (Write-Back)

```
Read:  App → Redis (always populated)
Write: App → Redis → (async) → Postgres
```

- Lowest write latency (Redis acknowledges immediately).
- Risk: data loss if Redis crashes before flushing to Postgres.
- Good for high-frequency writes where eventual persistence is acceptable (analytics, counters).

### 🔍 Try It Now: Write-Through Simulation

```redis
-- Write-through: update cache and database together
-- Step 1: Update Postgres (in terminal 1)
```

```sql
-- Terminal 1 (Postgres):
UPDATE events SET status = 'sold_out' WHERE id = 3;
```

```redis
-- Step 2: Immediately update Redis (in terminal 2)
-- This is the "write-through" part — both stores updated synchronously
HSET event:3 status "sold_out"
-- No stale data window!
```

### Comparison Table

| Pattern | Read Latency | Write Latency | Consistency | Complexity |
|---------|-------------|---------------|-------------|------------|
| Cache-Aside | Low (on hit) | Low (DB only) | Eventual (up to TTL) | Low |
| Write-Through | Low (always hit) | Higher (DB + cache) | Strong | Medium |
| Write-Behind | Low (always hit) | Lowest (cache only) | Eventual + risk | High |
| Read-Through | Low (on hit) | Low (DB only) | Eventual (up to TTL) | Low |

**Default choice:** Cache-aside with TTL. It's the simplest and covers 90% of cases. Switch to write-through only when read-after-write consistency matters (e.g., user updates their profile and immediately sees the old version).

---

## Part 6: Cache Hit Ratio and Monitoring (10 min)

### 📊 Observe: Redis Info

```redis
INFO stats
```

Look for these key metrics:

```
keyspace_hits:0
keyspace_misses:0
```

The **cache hit ratio** is: `hits / (hits + misses) * 100`

### 🔍 Try It Now: Build a Health Check

Let's simulate traffic and watch the hit ratio:

```redis
-- Reset stats
CONFIG RESETSTAT

-- Simulate 10 requests to the events listing
-- First request: MISS (cache is empty)
GET events:listing
-- (nil) — MISS

-- Fill the cache
SET events:listing '{"events":[]}' EX 300

-- Next 9 requests: HIT
GET events:listing
GET events:listing
GET events:listing
GET events:listing
GET events:listing
GET events:listing
GET events:listing
GET events:listing
GET events:listing

-- Check stats
INFO stats
```

Look for:
```
keyspace_hits:9
keyspace_misses:1
```

Hit ratio: 9 / (9 + 1) = **90%** — and that's with only 10 requests. In production, a properly cached endpoint should have 95-99% hit ratio.

### Monitor Memory Usage

```redis
INFO memory
```

Key metrics:
```
used_memory_human:1.50M
used_memory_peak_human:2.00M
maxmemory:0                    # 0 = no limit (dangerous in production!)
```

### 🔍 Try It Now: Check Key Count and Memory

```redis
-- Total keys in the database
DBSIZE

-- Memory used by a specific key
MEMORY USAGE events:listing

-- Find large keys (scan — non-blocking)
SCAN 0 COUNT 100

-- All keys matching a pattern (use SCAN in production, not KEYS)
SCAN 0 MATCH event:* COUNT 100
```

### Building a /health Endpoint (Conceptual)

A production health check endpoint would return:

```json
{
  "cache": {
    "status": "healthy",
    "hit_ratio": 0.97,
    "total_keys": 1523,
    "memory_used": "45MB",
    "memory_limit": "512MB",
    "uptime_seconds": 86400
  },
  "database": {
    "status": "healthy",
    "active_connections": 12,
    "max_connections": 100
  }
}
```

The data comes from:
- Redis: `INFO stats` (hit ratio), `INFO memory` (memory), `DBSIZE` (key count)
- Postgres: `SELECT count(*) FROM pg_stat_activity` (connections)

---

## Part 7: Cache Stampede Prevention (5 min)

### The Problem

Imagine your `events:listing` cache expires. At that exact moment, 500 concurrent requests arrive. All 500 see a cache miss. All 500 query Postgres simultaneously. Your database gets hammered.

This is called a **cache stampede** (or thundering herd).

### Solutions

**1. Locking (Mutex)**

```
FUNCTION get_events():
    cached = redis.GET("events:listing")
    if cached: return cached

    # Try to acquire a lock
    lock_acquired = redis.SET("events:listing:lock", "1", NX=True, EX=5)
    if lock_acquired:
        # This request rebuilds the cache
        data = postgres.query(...)
        redis.SET("events:listing", data, EX=300)
        redis.DEL("events:listing:lock")
        return data
    else:
        # Another request is rebuilding — wait and retry
        sleep(0.1)
        return get_events()  # retry
```

### 🔍 Try It Now: Redis Locking

```redis
-- Acquire a lock (NX = only if not exists)
SET events:listing:lock "rebuilding" NX EX 5
-- Returns: OK (lock acquired)

-- Another process tries to acquire
SET events:listing:lock "rebuilding" NX EX 5
-- Returns: (nil) — lock already held!

-- After rebuild, release
DEL events:listing:lock
```

**2. Probabilistic Early Expiration (XFetch)**

Instead of waiting for TTL to expire, refresh the cache early with increasing probability as TTL approaches zero. This ensures the cache is almost always warm.

**3. Stale-While-Revalidate**

Serve the stale cached data immediately while refreshing in the background. The user gets a fast (slightly stale) response, and the cache is updated for the next request.

For TicketPulse's scale, the locking approach is sufficient. XFetch and stale-while-revalidate are for extremely high-traffic scenarios (millions of requests per second).

---

## Part 8: Clean Up and Review (2 min)

```redis
-- In Redis: clear all test data
FLUSHDB
QUIT
```

```sql
-- In Postgres: revert the event name change
UPDATE events SET name = 'Jazz at the Fillmore: Jade Patel' WHERE id = 3;
UPDATE events SET status = 'on_sale' WHERE id = 3;

-- Drop the materialized view if you created one in M08
DROP MATERIALIZED VIEW IF EXISTS mv_popular_events;
```

---

## 🏁 Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **Cache-aside** | App checks cache, misses query DB, fills cache. Most common pattern. |
| **TTL** | Always set one. It's your safety net against stale data. Match TTL to data's change frequency. |
| **Invalidation** | TTL-based is simplest. Explicit DEL on write for fresher data. Always use TTL as backup. |
| **Write-through** | Write to cache + DB synchronously. Use when read-after-write consistency matters. |
| **Write-behind** | Write to cache, async to DB. Fastest writes, but risk of data loss. |
| **Hit ratio** | Target 95%+. Monitor with `INFO stats`. Low hit ratio = bad TTL or bad key design. |
| **Stampede** | Use locking (SET NX) to prevent hundreds of simultaneous cache rebuilds. |
| **Never cache without TTL** | A cache entry without TTL is a ticking time bomb of stale data. |

### The Caching Decision Checklist

Before caching a query, ask:
1. **Is the query actually slow?** (Measure first. Don't cache a 1ms query.)
2. **Is the data read more often than written?** (High read:write ratio = great cache candidate)
3. **How stale can it be?** (Determines TTL)
4. **What happens if a user sees stale data?** (Listing page: fine. Account balance: not fine.)
5. **How do I invalidate?** (TTL alone? Explicit invalidation on write?)

## What's Next

You've completed **Section 1B: Data Foundations**. You can now:
- Design relational schemas from requirements
- Write SQL with CTEs, window functions, and advanced aggregations
- Optimize queries with EXPLAIN ANALYZE and proper indexes
- Make normalization/denormalization trade-offs
- Use Redis for sessions, counters, and caching
- Implement cache-aside with proper TTL and invalidation

Next up is **Section 1C**, where you'll build on these foundations with application-level patterns.

## 📚 Further Reading
- [Redis Caching Patterns](https://redis.io/docs/manual/patterns/) — Official patterns documentation
- [Caching Strategies and How to Choose the Right One](https://codeahoy.com/2017/08/11/caching-strategies-and-how-to-choose-the-right-one/)
- Chapter 2 of the 100x Engineer Guide: Section 5 — Caching Strategies
- Martin Kleppmann, *Designing Data-Intensive Applications*, Chapter 5 (Replication)
- [MemoryDB for Redis](https://aws.amazon.com/memorydb/) — When you need Redis with durability
