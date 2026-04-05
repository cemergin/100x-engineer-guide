# L1-M09: NoSQL: When and Why

> **Loop 1 (Foundation)** | Section 1B: Data & Databases | ⏱️ 60 min | 🟢 Core | Prerequisites: L1-M05, L1-M06
>
> **Source:** Chapters 2, 24 of the 100x Engineer Guide

## What You'll Learn
- Redis fundamentals: data structures, commands, and use cases
- When key-value stores beat relational databases (and when they don't)
- How to move session storage from Postgres to Redis
- DynamoDB partition key design concepts
- Document databases: when MongoDB-style storage makes sense
- Polyglot persistence — using the right database for each access pattern

## Why This Matters
PostgreSQL is the right default for most data. But "most" is not "all." Sessions in Postgres means every page load hits your database with a point lookup that Redis handles 100x faster. View counters in Postgres means row-level locks on your hottest data. Choosing the wrong database for an access pattern creates performance problems that no amount of optimization can fix. This module teaches you when to reach for something other than Postgres.

## Prereq Check

You need Docker running with TicketPulse's Postgres from M05.

```bash
# Start Redis alongside Postgres
docker compose up -d redis

# Or standalone:
docker run -d \
  --name ticketpulse-redis \
  -p 6379:6379 \
  redis:7-alpine
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

Verify both are running:

```bash
docker ps | grep -E 'postgres|redis'
```

---

## Part 1: Redis Fundamentals (15 min)

### 🔍 Try It Now: Connect to Redis

```bash
docker exec -it ticketpulse-redis redis-cli
```

You should see:

```
127.0.0.1:6379>
```

Redis is an in-memory data structure store. Everything lives in RAM, which is why it's fast (sub-millisecond operations). Let's learn the core commands.

### Strings (Key-Value)

```redis
-- Set a key
SET greeting "Hello, TicketPulse"

-- Get it back
GET greeting
-- Returns: "Hello, TicketPulse"

-- Set with an expiration (TTL) — 60 seconds
SET session:abc123 "user_id:42" EX 60

-- Check remaining TTL
TTL session:abc123
-- Returns: ~59 (seconds remaining)

-- Check if a key exists
EXISTS session:abc123
-- Returns: 1 (true) or 0 (false)

-- Delete a key
DEL greeting
```

### 🔍 Try It Now: Atomic Counters

```redis
-- INCR: atomic increment (thread-safe, no race conditions)
SET event:1:views 0
INCR event:1:views
INCR event:1:views
INCR event:1:views
GET event:1:views
-- Returns: "3"

-- INCRBY: increment by a specific amount
INCRBY event:1:views 100
GET event:1:views
-- Returns: "103"

-- DECR / DECRBY: atomic decrement
DECR event:1:views
GET event:1:views
-- Returns: "102"
```

> **Pro tip:** `INCR` is atomic. If 1,000 users view an event page simultaneously, all 1,000 increments are applied correctly with zero locking, zero contention. Try doing that with `UPDATE events SET views = views + 1` in Postgres under load — you'll hit row-level lock contention.

### Hashes (Like a Row in a Table)

```redis
-- Store a structured object
HSET event:1 name "Aurora Flux: Synthesis Tour" venue "Madison Square Garden" tickets_sold 287

-- Get a single field
HGET event:1 name
-- Returns: "Aurora Flux: Synthesis Tour"

-- Get all fields
HGETALL event:1
-- Returns all key-value pairs

-- Increment a numeric field
HINCRBY event:1 tickets_sold 1
HGET event:1 tickets_sold
-- Returns: "288"

-- Check if a field exists
HEXISTS event:1 venue
-- Returns: 1
```

### Lists (Ordered, Duplicates Allowed)

```redis
-- Push items to a list (LPUSH = left/front, RPUSH = right/back)
LPUSH recent_orders "order:1001"
LPUSH recent_orders "order:1002"
LPUSH recent_orders "order:1003"

-- Get items by index range (0 = first, -1 = last)
LRANGE recent_orders 0 -1
-- Returns: ["order:1003", "order:1002", "order:1001"]

-- Get only the 2 most recent
LRANGE recent_orders 0 1
-- Returns: ["order:1003", "order:1002"]

-- Trim to keep only last 100 entries (useful for capped lists)
LTRIM recent_orders 0 99

-- Length of list
LLEN recent_orders
-- Returns: 3
```

### Sets (Unique, Unordered)

```redis
-- Track unique visitors to an event page
SADD event:1:visitors "user:42"
SADD event:1:visitors "user:55"
SADD event:1:visitors "user:42"  -- duplicate, ignored

-- Count unique visitors
SCARD event:1:visitors
-- Returns: 2

-- Check if a user visited
SISMEMBER event:1:visitors "user:42"
-- Returns: 1 (true)

-- All members
SMEMBERS event:1:visitors
-- Returns: ["user:42", "user:55"]
```

### Sorted Sets (Unique, Ordered by Score)

```redis
-- Leaderboard: events ranked by ticket sales
ZADD event_leaderboard 287 "event:1"
ZADD event_leaderboard 195 "event:2"
ZADD event_leaderboard 342 "event:3"
ZADD event_leaderboard 98 "event:4"

-- Top 3 events by sales (highest first)
ZREVRANGE event_leaderboard 0 2 WITHSCORES
-- Returns: event:3 (342), event:1 (287), event:2 (195)

-- Rank of a specific event
ZREVRANK event_leaderboard "event:1"
-- Returns: 1 (0-indexed, so second place)

-- Increment a score (atomic, like INCR for sorted sets)
ZINCRBY event_leaderboard 50 "event:2"
```

### 🔍 Try It Now: Expiration

```redis
-- Set a key that expires in 10 seconds
SET flash_sale "50% off Event 3" EX 10

-- Watch it countdown
TTL flash_sale
-- Wait a few seconds...
TTL flash_sale
-- Wait until it expires...
GET flash_sale
-- Returns: (nil) — it's gone

-- Set expiration on an existing key
SET promotion "Buy 2 get 1 free"
EXPIRE promotion 300  -- expire in 5 minutes
TTL promotion
```

---

## Part 2: Sessions — Moving from Postgres to Redis (10 min)

### The Problem with Postgres Sessions

Imagine TicketPulse stores sessions in Postgres:

```sql
-- In your Postgres session
CREATE TABLE sessions (
    id VARCHAR(128) PRIMARY KEY,
    user_id BIGINT NOT NULL,
    data JSONB,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Every single page load:
-- 1. SELECT * FROM sessions WHERE id = :session_id AND expires_at > NOW();
-- 2. UPDATE sessions SET data = :updated_data WHERE id = :session_id;
```

Problems:
- **Every page load hits Postgres** — sessions are the highest-frequency read/write operation
- **Expired session cleanup** requires periodic DELETE queries or a background job
- **Row-level locks** on session updates can cause contention under load
- **Disk I/O** for something that's ephemeral (sessions are temporary by nature)

### The Redis Solution

```redis
-- Store a session (in redis-cli)
SET session:a1b2c3d4 '{"user_id": 42, "cart": ["ticket:101", "ticket:102"], "name": "Alice Johnson"}' EX 3600

-- Read it (every page load)
GET session:a1b2c3d4

-- Update it
SET session:a1b2c3d4 '{"user_id": 42, "cart": ["ticket:101", "ticket:102", "ticket:103"], "name": "Alice Johnson"}' EX 3600

-- Extend expiration on activity (keep-alive)
EXPIRE session:a1b2c3d4 3600
```

### 🔍 Try It Now: Compare the Performance

```redis
-- In redis-cli, time a read operation
-- Redis doesn't have a built-in timer, but you can observe it's instant

SET session:test '{"user_id": 1}' EX 3600
GET session:test
-- Response is immediate — sub-millisecond

-- Now try reading 1000 times in a pipeline
-- (In a real app, each page load does one GET)
```

### Why Redis Wins for Sessions

| Factor | Postgres | Redis |
|--------|----------|-------|
| Read latency | ~1ms (with index, data in cache) | ~0.1ms |
| Write latency | ~2ms (WAL flush, index update) | ~0.1ms |
| Expiration | Manual cleanup job needed | Built-in TTL, automatic eviction |
| Connection cost | Heavy (process per connection) | Lightweight (single-threaded event loop) |
| Data on disk? | Yes (ACID durability) | Optional (RDB/AOF persistence) |

For sessions, you don't need ACID. If a session is lost, the user logs in again. Redis gives you 10x lower latency with zero maintenance.

### ⚠️ Common Mistake: Redis as Primary Database

Redis is amazing for caching, sessions, counters, and leaderboards. It is NOT a replacement for Postgres for your core data. Why?

- **RAM is expensive** — a 100GB Redis instance costs 10x more than 100GB on Postgres SSD
- **No complex queries** — no JOINs, no WHERE clauses on arbitrary columns, no aggregations
- **Persistence is optional** — data can be lost on crash (depending on configuration)
- **No ACID transactions** — no rollback, no isolation levels (Redis does have basic transactions with MULTI/EXEC, but they're not equivalent)

---

## Part 3: Build a View Counter (10 min)

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Build: Event View Counter with Redis

<details>
<summary>💡 Hint 1: Direction</summary>
Think about the overall approach before diving into implementation details.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Break the problem into smaller steps. What needs to happen first?
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Review the concepts from this section. The solution follows the same patterns demonstrated above.
</details>


Every time someone views an event page, we increment a counter. This is a perfect Redis use case — high frequency writes to a single key with no need for ACID.

### 🔍 Try It Now

```redis
-- Simulate page views for different events
INCR event:1:pageviews
INCR event:1:pageviews
INCR event:1:pageviews
INCR event:2:pageviews
INCR event:3:pageviews
INCR event:3:pageviews

-- Check counts
GET event:1:pageviews
-- Returns: "3"

MGET event:1:pageviews event:2:pageviews event:3:pageviews
-- Returns: ["3", "1", "2"]
```

### Daily View Counter with Automatic Expiration

```redis
-- Track views per event per day
-- Key format: event:{id}:views:{date}
INCR event:1:views:2026-03-24
INCR event:1:views:2026-03-24
INCR event:1:views:2026-03-24

-- Set TTL to auto-delete after 30 days (don't accumulate old data forever)
EXPIRE event:1:views:2026-03-24 2592000

-- Get today's views
GET event:1:views:2026-03-24
-- Returns: "3"
```

### Using a Hash for Structured Counters

```redis
-- Store multiple counters for an event in one hash
HINCRBY event:1:stats pageviews 1
HINCRBY event:1:stats unique_visitors 1
HINCRBY event:1:stats add_to_cart 0

-- Simulate activity
HINCRBY event:1:stats pageviews 1
HINCRBY event:1:stats pageviews 1
HINCRBY event:1:stats unique_visitors 1
HINCRBY event:1:stats add_to_cart 1

-- Get all stats at once
HGETALL event:1:stats
-- Returns: pageviews=3, unique_visitors=2, add_to_cart=1
```

### Leaderboard: Most Viewed Events

```redis
-- Every page view also updates the leaderboard
ZINCRBY event_views_leaderboard 1 "event:1"
ZINCRBY event_views_leaderboard 1 "event:1"
ZINCRBY event_views_leaderboard 1 "event:1"
ZINCRBY event_views_leaderboard 1 "event:2"
ZINCRBY event_views_leaderboard 1 "event:3"
ZINCRBY event_views_leaderboard 1 "event:3"

-- Top 3 most viewed
ZREVRANGE event_views_leaderboard 0 2 WITHSCORES
-- Returns: event:1 (3), event:3 (2), event:2 (1)
```

---

## Part 4: DynamoDB Concepts (10 min)

DynamoDB is AWS's fully managed NoSQL database. You don't need to run it locally, but understanding its design principles is valuable because partition key design applies to many distributed systems.

### The Core Concept: Partition Key Design

DynamoDB distributes data across partitions based on the **partition key**. All items with the same partition key live on the same partition.

```
Table: TicketPulse_Orders

Partition Key: customer_email
Sort Key: ordered_at

Partition 1 (hash range 0x0000-0x5555):
  alice@example.com | 2026-04-01 | {order data}
  alice@example.com | 2026-04-05 | {order data}

Partition 2 (hash range 0x5556-0xAAAA):
  bob@example.com   | 2026-04-02 | {order data}
  carol@example.com | 2026-04-03 | {order data}

Partition 3 (hash range 0xAAAB-0xFFFF):
  dave@example.com  | 2026-04-04 | {order data}
  eve@example.com   | 2026-04-05 | {order data}
```

**Access patterns this design supports efficiently:**
- Get all orders for `alice@example.com` (partition key lookup)
- Get orders for `alice@example.com` after `2026-04-01` (partition key + sort key range)

**Access patterns it does NOT support:**
- Get all orders placed today (requires scanning every partition)
- Get orders sorted by total amount (sort key is `ordered_at`, not `total`)

### 🤔 Reflect: Partition Key Design for TicketPulse

If you were designing a DynamoDB table for TicketPulse tickets:

**Option A:** Partition Key = `event_id`
- Good: "Get all tickets for event 1" is a single partition read
- Bad: Popular events create hot partitions (event at MSG with 20K tickets all on one partition)

**Option B:** Partition Key = `event_id`, Sort Key = `ticket_id`
- Same as A, but allows range queries on ticket_id

**Option C:** Partition Key = `event_id#section`, Sort Key = `row#seat`
- Distributes tickets across more partitions
- Supports: "Get all Floor tickets for event 1"
- But: "Get all tickets for event 1" requires querying multiple partitions

**Key principle:** In DynamoDB, you design tables around your access patterns. In Postgres, you normalize and let indexes + JOINs handle any query. This is the fundamental difference.

---

## Part 5: Document Databases (5 min)

### When MongoDB-Style Documents Make Sense

Document databases store data as JSON-like documents with flexible schemas. They shine when:

1. **Schema varies per record** — e.g., product catalogs where a laptop has different fields than a t-shirt
2. **You always read/write the entire document** — e.g., user profiles loaded all at once
3. **Nested data is natural** — e.g., a blog post with embedded comments
4. **Rapid prototyping** — schema changes require no migrations

### When Documents Don't Make Sense

```json
// BAD: Storing TicketPulse orders as documents
{
  "order_id": 1,
  "customer": { "name": "Alice", "email": "alice@example.com" },
  "items": [
    {
      "ticket": {
        "event": { "name": "Aurora Flux Tour", "venue": { "name": "MSG" } },
        "section": "Floor", "seat": "S1", "price": 150.00
      }
    }
  ]
}
```

Problems with this approach:
- **Data duplication** — "MSG" is stored in every order for that venue
- **Update anomalies** — venue name change requires updating every order document
- **No JOINs** — "total revenue per venue" requires reading every order document
- **Aggregation is expensive** — "top 10 events by revenue" means scanning the entire collection

**Rule of thumb:** If your data has clear relationships between entities (venues ↔ events ↔ tickets ↔ orders), use a relational database. If your data is self-contained documents read/written as units, consider a document database.

---

## Part 6: Polyglot Persistence (5 min)

### 📐 Design: Which Parts of TicketPulse Belong Where?

<details>
<summary>💡 Hint 1: Direction</summary>
Think about the overall approach before diving into implementation details.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Break the problem into smaller steps. What needs to happen first?
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Review the concepts from this section. The solution follows the same patterns demonstrated above.
</details>


Polyglot persistence means using the right database for each access pattern. Here's how TicketPulse might split its data:

| Data | Database | Why |
|------|----------|-----|
| Events, venues, artists, tickets, orders | **PostgreSQL** | Relational data with complex queries, JOINs, transactions. ACID required for ticket purchases. |
| User sessions | **Redis** | High-frequency reads/writes, ephemeral, TTL-based expiration |
| Page view counters | **Redis** | Atomic increments, no durability needed, real-time leaderboards |
| Event search (full-text) | **PostgreSQL** (tsvector) or **Elasticsearch** | If search is simple, Postgres tsvector is enough. If you need faceted search, autocomplete, fuzzy matching — Elasticsearch. |
| Event images/media | **S3** (object storage) | Binary blobs don't belong in any database |
| Analytics/clickstream | **ClickHouse** or **BigQuery** | Append-only, columnar, optimized for aggregation over billions of events |
| Real-time notifications | **Redis Pub/Sub** or **Kafka** | Fan-out messaging, not storage |

### ⚠️ Common Mistake: Too Many Databases

Polyglot persistence is powerful but has a cost:
- Each database is another system to operate, monitor, back up, and upgrade
- Data consistency across databases requires explicit coordination (Saga pattern, outbox pattern)
- Developer cognitive load increases with each new technology

**Start with Postgres + Redis.** That covers 90% of use cases. Add specialized databases only when you have a measured need.

### 🤔 Reflect

Think about an application you've worked on or used. What data would benefit from being in a different database than where it currently lives? What would the migration look like?

---

## Part 7: Clean Up (2 min)

```redis
-- In redis-cli: clear all test data
FLUSHDB

-- Verify
DBSIZE
-- Returns: 0

-- Exit redis-cli
QUIT
```

Keep both containers running — we need Redis for the next module on caching.

---


> **What did you notice?** Look back at what you just built. What surprised you? What felt harder than expected? That's where the real learning happened.

## 🏁 Module Summary

| Technology | Best For | Not For |
|-----------|---------|---------|
| **PostgreSQL** | Relational data, complex queries, transactions, ACID | High-frequency counters, ephemeral data, sub-ms latency requirements |
| **Redis** | Sessions, caching, counters, leaderboards, pub/sub | Primary data store, complex queries, data > RAM size |
| **DynamoDB** | Massive scale key-value/document with predictable performance | Ad-hoc queries, JOINs, analytics |
| **MongoDB** | Flexible schemas, document-oriented access, rapid prototyping | Highly relational data, complex aggregations at scale |

**Key Redis commands to remember:**

| Command | Purpose |
|---------|---------|
| `SET` / `GET` | Store and retrieve strings |
| `INCR` / `DECR` | Atomic counters |
| `HSET` / `HGET` / `HGETALL` | Hash (structured data) operations |
| `LPUSH` / `LRANGE` | List operations |
| `SADD` / `SCARD` / `SISMEMBER` | Set operations |
| `ZADD` / `ZREVRANGE` / `ZINCRBY` | Sorted set (leaderboard) operations |
| `EX` / `EXPIRE` / `TTL` | Expiration management |

**The decision framework:** Start with Postgres for everything. Move specific access patterns to Redis when you have evidence that Postgres is the bottleneck for that pattern. Add other databases only when the access pattern truly can't be served well by Postgres or Redis.

## What's Next

In **L1-M10: Caching Strategies**, you'll combine Postgres and Redis into a caching layer — implementing cache-aside, managing TTLs, handling cache invalidation, and observing cache hit ratios in real time.

## Key Terms

| Term | Definition |
|------|-----------|
| **Key-value store** | A NoSQL database that stores data as simple key-value pairs, optimized for fast lookups by key. |
| **Document database** | A NoSQL database that stores data as semi-structured documents (typically JSON), allowing flexible schemas. |
| **TTL** | Time to Live; an expiration time after which a stored record is automatically deleted. |
| **Redis** | An in-memory data structure store commonly used as a cache, message broker, or key-value database. |
| **Polyglot persistence** | The practice of using different database technologies for different data storage needs within a single system. |

## 📚 Further Reading
- [Redis Documentation](https://redis.io/docs/) — Official docs with interactive examples
- [Try Redis](https://try.redis.io/) — Browser-based Redis tutorial
- [DynamoDB Guide](https://www.dynamodbguide.com/) — Alex DeBrie's excellent DynamoDB resource
- Chapter 2 of the 100x Engineer Guide: Sections 1.2 (NoSQL), 2.6 (Polyglot Persistence), 5 (Caching Strategies)
- Martin Kleppmann, *Designing Data-Intensive Applications*, Chapter 2 (Data Models)
