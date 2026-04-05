# L3-M63: Database at Scale

> **Loop 3 (Mastery)** | Section 3A: Global Scale Architecture | ⏱️ 90 min | 🟡 Deep Dive | Prerequisites: L2-M37 (PostgreSQL Internals), L2-M35 (Database Per Service), L3-M61 (Multi-Region Design)
>
> **Source:** Chapters 1, 19, 22, 23, 24 of the 100x Engineer Guide

---

## Why This Matters

Every application eventually outgrows its single database. The symptoms are always the same: queries that used to take 5ms now take 500ms. CPU is pegged during flash sales. Your analytics team's reporting queries are making your ops team's pagers go off. The database that served you well at 100,000 rows starts groaning at 50,000,000.

The instinct is to reach for the biggest instance type, or jump straight to sharding. Both are expensive mistakes. The real skill is knowing which scaling strategy to apply first, in what order, and at what thresholds — because each step adds complexity, and complexity is where bugs live.

> **Ecosystem note:** Chapter 24 of the 100x Engineer Guide goes deep on PostgreSQL internals: MVCC, WAL, the query planner, and vacuum mechanics. This module is the applied companion — you will read about those mechanisms and then use them to make real scaling decisions for TicketPulse.

---

## The Goal

TicketPulse has grown. The numbers:
- 50 million tickets in the database
- 10 million orders
- 1 million events
- 500 queries per second on the tickets table
- Single PostgreSQL instance: 16 vCPU, 64GB RAM, 2TB SSD

The symptoms:
- `SELECT * FROM tickets WHERE event_id = ? AND status = 'available'` takes 200ms (was 5ms).
- Sequential scans on the tickets table during peak load.
- Replication lag to read replicas spiking to 30 seconds during bulk operations.
- Database CPU at 85% during flash sales.
- Nightly analytics queries block write performance.

Single Postgres is struggling. You need to scale the database. This module covers three levels of database scaling, from simplest to most complex: read replicas, partitioning, and sharding.

**By the end, you will have a scaling strategy that handles 10x the current load.**

---

## 0. The Scaling Ladder (5 minutes)

Before you reach for complex solutions, understand the progression:

```
Level 0: Optimize queries and indexes          (free — always do this first)
Level 1: Read replicas                         (medium complexity)
Level 2: Table partitioning (within one DB)    (medium complexity)
Level 3: Sharding (across multiple DBs)        (high complexity)
```

Each level has a cost in complexity. Never jump to Level 3 when Level 1 would suffice. Most applications never need sharding. Many applications at significant scale run on a single well-tuned PostgreSQL with read replicas and partitioning.

### 🤔 Before You Read On

Which of TicketPulse's symptoms above can be solved with read replicas? Which require partitioning? Which might require sharding?

Write your hypotheses before reading. The act of guessing before you know forces your brain to engage with the problem rather than passively receive the answer.

---

## 1. Read Replicas (20 minutes)

### The Pattern

```
                    ┌─────────────────┐
                    │   Application   │
                    └────┬───────┬────┘
                         │       │
                    Writes│       │Reads
                         │       │
                ┌────────▼──┐  ┌─▼─────────────┐
                │  Primary  │  │ Read Replica 1 │
                │ (Leader)  │──│ Read Replica 2 │
                │           │  │ Read Replica 3 │
                └───────────┘  └────────────────┘
                  async replication
```

All writes go to the primary. Reads can be distributed across replicas. This effectively multiplies your read capacity by the number of replicas.

### 📐 Design Exercise: Query Routing

<details>
<summary>💡 Hint 1: Direction</summary>
Have you considered applying a "read-your-writes" window? Any read within a few seconds of a user's own write should hit the primary, while stale-tolerant browsing reads go to replicas.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Writes and atomicity-dependent reads (ticket reservation, order insert) always hit primary. Analytics aggregations always hit a dedicated replica. The tricky one is "available ticket count" -- it depends on whether you are displaying it or gating a purchase on it.
</details>


Classify these TicketPulse queries. Which MUST hit the primary? Which can safely go to a replica?

1. `SELECT * FROM events WHERE city = 'London' AND date > NOW()`
2. `UPDATE tickets SET status = 'reserved' WHERE id = ? AND status = 'available'`
3. `SELECT COUNT(*) FROM tickets WHERE event_id = ? AND status = 'available'`
4. `INSERT INTO orders (user_id, ticket_id, amount) VALUES (?, ?, ?)`
5. `SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC`
6. `SELECT e.name, COUNT(t.id) FROM events e JOIN tickets t ON t.event_id = e.id GROUP BY e.name`

**Reference Answers:**

| Query | Primary or Replica? | Reason |
|---|---|---|
| 1. Browse events | Replica | Eventually consistent is fine for browsing. Stale by a few seconds is acceptable. |
| 2. Reserve ticket | **Primary** | This is a write and a critical consistency operation. Must hit primary. |
| 3. Available ticket count | **Depends** | For display purposes (browsing): replica is fine. For the purchase flow (checking before reserving): must hit primary. |
| 4. Insert order | **Primary** | All writes go to primary. |
| 5. User's order history | Replica | Slight staleness is acceptable. But apply **read-your-writes** — right after placing an order, route to primary so the user sees their new order immediately. |
| 6. Analytics aggregation | Replica | Expensive query that should never hit primary. This is exactly what replicas are for. |

### Replication Lag: The Silent Danger

The most insidious failure mode of read replicas is replication lag. During peak write load, replicas can fall behind. A user places an order, refreshes, and their order is not there yet (because they hit a replica that has not received the write).

But replication lag has a deeper danger: overselling. If your ticket availability check hits a replica that is 30 seconds behind, you might show a concert as having 50 tickets available when the primary already sold 45 of them. The user successfully adds to cart, attempts checkout, and then gets an error at the moment of purchase. That failure is expensive — lost revenue, support tickets, and damaged trust.

**The Replication Lag Runbook**

When replication lag spikes, you need to know exactly what is happening and have a response:

```sql
-- Step 1: Check current lag on each replica
SELECT
  client_addr,
  state,
  sent_lsn,
  write_lsn,
  flush_lsn,
  replay_lsn,
  write_lag,
  flush_lag,
  replay_lag
FROM pg_stat_replication;

-- Step 2: Check lag from the replica side
-- (run on the replica itself)
SELECT
  now() - pg_last_xact_replay_timestamp() AS replication_lag,
  pg_is_in_recovery() as is_replica;

-- Step 3: Find the WAL position difference
SELECT
  pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes
FROM pg_stat_replication;
```

**Strategies for Managing Replication Lag:**

1. **Read-your-writes consistency:** After a write, route the user's subsequent reads to the primary for a short window (e.g., 5 seconds). Implement via a session flag or sticky routing.

2. **Lag-aware routing:** If a replica's lag exceeds a threshold (e.g., 5 seconds), stop sending it traffic until it catches up.

3. **Asynchronous analytics offloading:** The biggest cause of replication lag is bulk operations like nightly reporting queries. Move analytics to a dedicated replica that is allowed to lag. Never let analytics compete with transactional reads.

4. **Connection pooling with PgBouncer:** Replicas under connection pressure lag more, because context-switching and lock contention slow down WAL replay. PgBouncer pools connections, reducing per-replica pressure.

```sql
-- Alert rule: lag exceeding 5 seconds is dangerous
-- Alert rule: lag exceeding 30 seconds on a replica serving transaction reads is an incident
SELECT
  CASE
    WHEN EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) > 30
      THEN 'CRITICAL: replica is > 30 seconds behind'
    WHEN EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) > 5
      THEN 'WARNING: replica lag exceeds threshold'
    ELSE 'OK'
  END AS lag_status,
  ROUND(EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))::numeric, 2) AS lag_seconds;
```

### 🤔 Prediction Prompt

Before looking at the lag-aware pool implementation, sketch out what data you would need to make routing decisions. How would you detect a lagging replica without adding latency to every request?

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Build: Lag-Aware Connection Pool

<details>
<summary>💡 Hint 1: Direction</summary>
Have you considered polling replica lag on a background interval (every 10s) rather than checking on every request? The lag check itself is a query -- you do not want it on the hot path.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Query `pg_last_xact_replay_timestamp()` on each replica periodically. If the delta exceeds your threshold (e.g., 5 seconds), remove that replica from the routing pool. Fall back to primary if all replicas are lagging.
</details>


Here is a TypeScript sketch of lag-aware routing logic. This wraps your database client and automatically routes reads away from lagging replicas:

```typescript
interface ReplicaStatus {
  url: string;
  lagSeconds: number;
  healthy: boolean;
  lastChecked: Date;
}

class LagAwarePool {
  private primary: DatabaseClient;
  private replicas: ReplicaStatus[];
  private readonly LAG_THRESHOLD_SECONDS = 5;

  async getReadConnection(requireFreshData = false): Promise<DatabaseClient> {
    // Reads that require fresh data (e.g., right after a write) hit primary
    if (requireFreshData) {
      return this.primary;
    }

    // Find a healthy replica with acceptable lag
    const healthyReplica = this.replicas.find(
      r => r.healthy && r.lagSeconds < this.LAG_THRESHOLD_SECONDS
    );

    if (!healthyReplica) {
      // All replicas lagging or unhealthy — fall back to primary
      console.warn('All replicas lagging, routing read to primary');
      return this.primary;
    }

    return new DatabaseClient(healthyReplica.url);
  }

  async refreshReplicaStatus(): Promise<void> {
    // Called on a 10-second interval by a health-check loop
    for (const replica of this.replicas) {
      try {
        const client = new DatabaseClient(replica.url);
        const result = await client.query(
          `SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))::numeric AS lag_seconds`
        );
        replica.lagSeconds = parseFloat(result.rows[0].lag_seconds);
        replica.healthy = true;
        replica.lastChecked = new Date();
      } catch (err) {
        replica.healthy = false;
      }
    }
  }
}
```

### 🤔 Reflect: Replication Lag Scenarios

Work through these scenarios mentally before reading the analysis:

**Scenario A:** It is 11:59 PM on a Friday. TicketPulse is running a nightly report that computes event revenue for the month. The query takes 8 minutes and runs on the primary. Replication lag to replica 1 spikes to 45 seconds. A user tries to buy a ticket. What happens?

**Scenario B:** You add a third read replica to handle Black Friday traffic. But 30 seconds after the big sale starts, replica 3 starts showing 20-second lag. Replica 1 and 2 are at 1 second. Your routing logic is round-robin. What percentage of users see stale data?

**Answers:**
- Scenario A: The replica is 45 seconds behind. If your ticket availability check routes to the replica, a user might see "200 tickets available" when only 150 actually remain. The fix: run that analytics query on a dedicated analytics replica that is explicitly excluded from transactional routing. Never run long-running reports on replicas that serve live traffic.
- Scenario B: With round-robin across 3 replicas, 33% of reads hit replica 3 (the lagging one). With lag-aware routing, replica 3 would be excluded, and load shifts to replicas 1 and 2 — 50/50. You trade some load distribution for data freshness. This is the right trade-off.

---

## 2. Connection Pool Tuning (10 minutes)

Before jumping to partitioning or sharding, many teams miss a critical bottleneck: connection limits. PostgreSQL has a finite number of concurrent connections. When your connection pool is saturated, queries queue and latency spikes — even if the database itself has headroom.

### The Math

```
PostgreSQL default max_connections = 100

Each connection reserves:
  - ~5-10 MB of shared memory
  - A backend process

At 100 connections with 64GB RAM:
  - Connections: 1,000 MB for connection overhead
  - Available for data/indexes: ~63 GB

At 500 connections (if you raise max_connections):
  - Connections: 5,000 MB — 5GB gone to overhead
  - Each additional connection context-switch slows ALL queries
```

This is why raising `max_connections` is not free. Beyond ~300 connections on even a large instance, PostgreSQL's performance degrades due to lock contention and context switching.

### PgBouncer: The Connection Multiplexer

PgBouncer sits between your application and PostgreSQL. Your app thinks it has 1,000 connections. PgBouncer actually uses 50 connections to PostgreSQL, multiplexing client requests across them.

```
App instances (1,000 "connections" to PgBouncer)
        │
        ▼
   PgBouncer (50 actual PostgreSQL connections)
        │
        ▼
   PostgreSQL (max_connections = 100, now has headroom)
```

```ini
# pgbouncer.ini — essential configuration
[databases]
ticketpulse = host=postgres-primary port=5432 dbname=ticketpulse

[pgbouncer]
pool_mode = transaction          # One connection per transaction (not per session)
max_client_conn = 2000           # App can have up to 2000 "connections"
default_pool_size = 50           # But only 50 real connections to Postgres
min_pool_size = 10               # Keep at least 10 warm connections
server_idle_timeout = 600        # Drop idle server connections after 10 min
client_idle_timeout = 300        # Drop idle client connections after 5 min
```

**pool_mode choices:**

| Mode | When a Server Connection Is Held | Overhead | Use For |
|---|---|---|---|
| `session` | For the entire client session | High | Legacy apps that use session state |
| `transaction` | For the duration of a transaction | Low | Most modern apps — use this |
| `statement` | For a single statement | Lowest | Only if you never use transactions |

Use `transaction` mode for TicketPulse. Each request gets a server connection only while executing a transaction. Between requests, the connection returns to the pool.

### 📐 Tuning Exercise: Right-Size the Pool

<details>
<summary>💡 Hint 1: Direction</summary>
Have you considered that raising `max_connections` past ~300 on PostgreSQL degrades performance due to lock contention? PgBouncer in transaction mode is the multiplexer that decouples client connections from server connections.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Reserve 20 connections for admin/migrations. Divide the remaining 180 across your services. PgBouncer `max_client_conn` can be 2000+ safely since client connections are cheap -- the expensive resource is the server-side pool.
</details>


Given:
- 3 app pods, each with 10 concurrent workers
- 1 PostgreSQL primary
- PostgreSQL `max_connections = 200`

Fill in the blanks:

```
Total app worker threads: ______ (3 × 10)
Ideal pool size per service: ______
  (leave 20 connections for admin access, split remainder across services)
PgBouncer max_client_conn: ______
  (higher is fine — PgBouncer handles many idle clients cheaply)
```

**Answers:** 30 total workers. With `max_connections = 200`, reserve 20 for admin/migrations, leaving 180 for the app. 60 connections per service (if 3 services). PgBouncer `max_client_conn = 2000` — clients are cheap, server connections are expensive.

---

## 3. Table Partitioning (20 minutes)

### The Problem with One Big Table

The tickets table has 50 million rows. Even with indexes, certain operations suffer:
- **Vacuum and autovacuum** must process the entire table. This causes I/O spikes.
- **Index bloat** — indexes grow large and less cache-friendly.
- **Bulk operations** (deleting old data) require scanning massive indexes.
- **Sequential scans** for queries that hit too many rows for an index to help.

Partitioning splits one logical table into multiple physical tables (partitions). Each partition is an independent table with its own indexes and storage. PostgreSQL routes queries to the relevant partition(s) automatically.

### 🛠️ Build: Partition the Tickets Table

<details>
<summary>💡 Hint 1: Direction</summary>
Think about which column appears in almost every query's WHERE clause AND has a natural ordering that separates hot data from cold data.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Range partition by event_date using quarterly boundaries. Create a DEFAULT partition as a safety net for any rows that fall outside defined ranges.
</details>

The tickets table has a natural partitioning dimension: time. Events happen on specific dates. Old events (and their tickets) are rarely queried. Current and upcoming events are hot.

```sql
-- Step 1: Create the partitioned table
CREATE TABLE tickets (
    id              UUID NOT NULL,
    event_id        UUID NOT NULL,
    event_date      DATE NOT NULL,
    seat_section    VARCHAR(50),
    seat_row        VARCHAR(10),
    seat_number     INT,
    tier            VARCHAR(30) NOT NULL,
    price_in_cents  BIGINT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'available',
    reserved_by     UUID,
    reserved_at     TIMESTAMP,
    purchased_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (event_date);

-- Step 2: Create partitions for each quarter
CREATE TABLE tickets_2025_q1 PARTITION OF tickets
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE tickets_2025_q2 PARTITION OF tickets
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE tickets_2025_q3 PARTITION OF tickets
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE tickets_2025_q4 PARTITION OF tickets
    FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');

CREATE TABLE tickets_2026_q1 PARTITION OF tickets
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');

CREATE TABLE tickets_2026_q2 PARTITION OF tickets
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');

-- Step 3: Create a DEFAULT partition for anything that doesn't match
CREATE TABLE tickets_default PARTITION OF tickets DEFAULT;

-- Step 4: Create indexes on each partition (PostgreSQL does this automatically
-- if you create the index on the parent table)
CREATE INDEX idx_tickets_event_id ON tickets (event_id);
CREATE INDEX idx_tickets_status ON tickets (status) WHERE status = 'available';
CREATE INDEX idx_tickets_event_status ON tickets (event_id, status);
```

### 📊 Observe: Partition Pruning

The power of partitioning is **partition pruning** — PostgreSQL skips partitions that cannot contain matching rows.

```sql
-- Query: Find available tickets for an event on 2026-03-15
EXPLAIN ANALYZE
SELECT * FROM tickets
WHERE event_date = '2026-03-15'
  AND event_id = 'abc-123'
  AND status = 'available';

-- BEFORE partitioning:
-- Seq Scan on tickets  (cost=0.00..1250000.00 rows=50 width=200)
--   Filter: (event_date = '2026-03-15' AND event_id = 'abc-123' AND status = 'available')
--   Rows Removed by Filter: 49999950
--   Planning Time: 0.5 ms
--   Execution Time: 3200 ms

-- AFTER partitioning:
-- Index Scan using tickets_2026_q1_event_id_idx on tickets_2026_q1
--   Index Cond: (event_id = 'abc-123')
--   Filter: (status = 'available')
--   Planning Time: 0.3 ms
--   Execution Time: 0.8 ms
```

The query only hits `tickets_2026_q1` because PostgreSQL knows that `event_date = '2026-03-15'` can only be in that partition. 49 million rows in other partitions are never touched. This is the magic of partition pruning.

### ⚠️ Partition Pruning Pitfalls

Partition pruning only works when the query's WHERE clause includes the partition key in a form PostgreSQL can evaluate at planning time. These patterns BREAK pruning:

```sql
-- WORKS: Literal value — planner knows which partition at plan time
SELECT * FROM tickets WHERE event_date = '2026-03-15';

-- WORKS: Parameter placeholder — planner assumes a specific partition
SELECT * FROM tickets WHERE event_date = $1;

-- BREAKS PRUNING: Function on the partition key
SELECT * FROM tickets WHERE date_trunc('month', event_date) = '2026-03-01';
-- Planner cannot evaluate date_trunc('month', event_date) at plan time
-- Scans ALL partitions

-- BREAKS PRUNING: Implicit cast that changes the type
SELECT * FROM tickets WHERE event_date = '2026-03-15'::text;
-- Type mismatch prevents pruning
```

**The fix:** Always filter on the partition key directly, without wrapping functions. If you need to filter by month, store a `event_month` column (or use a composite partition key).

### 🤔 Reflect: Automating Partition Creation

If TicketPulse sells tickets for events 2 years in advance, you need partitions ready before data arrives. A common pattern is a scheduled job that pre-creates partitions:

```sql
-- Run monthly via pg_cron or a scheduled Lambda
CREATE OR REPLACE FUNCTION create_future_partition()
RETURNS void AS $$
DECLARE
  next_quarter_start DATE;
  next_quarter_end DATE;
  partition_name TEXT;
BEGIN
  -- Calculate the start of 2 quarters from now
  next_quarter_start := date_trunc('quarter', now() + interval '6 months');
  next_quarter_end := next_quarter_start + interval '3 months';
  partition_name := 'tickets_' || to_char(next_quarter_start, 'YYYY_"q"Q');

  -- Create if not exists
  EXECUTE format(
    'CREATE TABLE IF NOT EXISTS %I PARTITION OF tickets FOR VALUES FROM (%L) TO (%L)',
    partition_name, next_quarter_start, next_quarter_end
  );

  RAISE NOTICE 'Partition % is ready', partition_name;
END;
$$ LANGUAGE plpgsql;
```

What happens if no partition exists for a row being inserted? It goes into `tickets_default`. This is a safety net, but data in the default partition gets no partition pruning benefit — queries will always scan it. Monitor the default partition size. If rows accumulate there, your partition creation automation has a bug.

### Archiving Old Data

One of the biggest wins of partitioning: archiving old data is instant.

```sql
-- Detach the old partition (instant — just metadata change)
ALTER TABLE tickets DETACH PARTITION tickets_2025_q1;

-- Move it to cheaper storage, archive it, or drop it
-- This does not block any queries on other partitions
DROP TABLE tickets_2025_q1;  -- Gone. No vacuum needed.
```

Compare this with deleting old rows without partitioning:
```sql
-- Without partitioning: delete 10M rows
DELETE FROM tickets WHERE event_date < '2025-04-01';
-- This takes minutes, generates massive WAL, triggers vacuum, and blocks writes.
```

### Partition Key Choice

| Partition Key | Strategy | When to Use |
|---|---|---|
| `event_date` (range) | Range partitioning by quarter/month | Time-series data. Old partitions can be archived. |
| `venue_region` (list) | List partitioning by region | Multi-region deployments where queries are region-scoped. |
| `event_id` (hash) | Hash partitioning across N partitions | Even distribution when no natural range exists. |

**For TicketPulse:** Range partitioning by `event_date` is the best choice. Queries almost always filter by event date (directly or through event_id which maps to a date). Old events become cold data that can be archived.

### 🛠️ Hands-On: Verify Autovacuum Improvements

<details>
<summary>💡 Hint 1: Direction</summary>
Have you considered that smaller partitions may need a lower `autovacuum_vacuum_scale_factor`? The default (0.2 = 20% of table dead tuples) on a 3M-row partition means autovacuum triggers after 600K dead tuples -- that might be too late.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Query `pg_stat_user_tables` filtered by `tablename LIKE 'tickets_%'` and check `n_dead_tup` and `last_autovacuum` per partition. A healthy setup shows recent autovacuum timestamps and near-zero dead tuples on active partitions.
</details>


After partitioning, check that autovacuum is running on individual partitions rather than the whole table:

```sql
-- Before: autovacuum runs on a 50M row table, taking 20+ minutes
-- After: autovacuum runs on individual ~3M row partitions, taking 2 minutes each

-- Check autovacuum stats per partition
SELECT
  schemaname,
  tablename,
  n_dead_tup,
  last_autovacuum,
  last_autoanalyze,
  autovacuum_count
FROM pg_stat_user_tables
WHERE tablename LIKE 'tickets_%'
ORDER BY n_dead_tup DESC;
```

A healthy partitioned table should show recent autovacuum timestamps on each active partition and near-zero dead tuples. If a partition has a high dead tuple count and no recent autovacuum, check your `autovacuum_vacuum_scale_factor` — smaller partitions may need a lower threshold.

---

## 4. Sharding (25 minutes)

### When Partitioning Is Not Enough

Partitioning splits data within one database server. The server still has finite CPU, memory, and I/O. When you hit these limits — when a single PostgreSQL instance, no matter how large, cannot handle the write throughput — you need sharding.

Sharding splits data across multiple independent database servers. Each shard is a complete database that handles a subset of the data.

```
                    ┌─────────────────┐
                    │   Application   │
                    │   (Router)      │
                    └────┬───┬───┬────┘
                         │   │   │
                ┌────────▼┐ ┌▼──────┐ ┌▼────────┐
                │ Shard 0 │ │Shard 1│ │ Shard 2 │
                │ (DB)    │ │ (DB)  │ │  (DB)   │
                └─────────┘ └───────┘ └─────────┘
```

### 📐 Design Exercise: Choose a Shard Key

<details>
<summary>💡 Hint 1: Direction</summary>
Have you considered which access pattern dominates? TicketPulse's hot path is per-event (browse tickets, reserve, purchase). The shard key should make that path shard-local.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
Shard by `event_id`. The entire purchase flow (lookup, availability check, reserve, confirm) stays on one shard. Cross-shard queries like "all orders for user X" are the cold path -- handle them with a secondary index or CQRS read model.
</details>


This is the most important decision in sharding. The shard key determines which shard stores each row. A bad shard key creates hotspots, expensive cross-shard queries, and operational nightmares.

**Evaluate these shard key candidates for TicketPulse's tickets table:**

| Shard Key | Distribution | Query Locality | Cross-Shard Queries |
|---|---|---|---|
| `venue_region` | ??? | ??? | ??? |
| `event_id` | ??? | ??? | ??? |
| `user_id` | ??? | ??? | ??? |
| `ticket_id` (hash) | ??? | ??? | ??? |

Fill in each cell before reading the analysis.

### Analysis

**`venue_region` (e.g., americas, europe, asia-pacific):**
- Distribution: Uneven. Americas probably has 60% of tickets. Hotspot risk.
- Query locality: Excellent for "show tickets for events in this region." All data for a region is on one shard.
- Cross-shard queries: "Show all orders for user X" spans all shards if the user bought tickets in multiple regions.
- **Verdict:** Good for multi-region architecture (aligns with M61), but only 3 shards means limited scaling.

**`event_id`:**
- Distribution: Good if events are spread evenly. Some large events (Taylor Swift) create hotspots.
- Query locality: Excellent. All tickets for an event are on one shard. Purchase flow is shard-local.
- Cross-shard queries: "Show all orders for user X" spans shards. "Show all events" spans shards.
- **Verdict:** Strong choice. Aligns with TicketPulse's access pattern (most operations are per-event).

**`user_id`:**
- Distribution: Good (many users).
- Query locality: Excellent for "show all orders for user X." Terrible for "show available tickets for event Y" (tickets for one event are scattered across all shards).
- Cross-shard queries: Every event-based query spans all shards. This is the most common query.
- **Verdict:** Bad choice for TicketPulse. User-centric queries are less common than event-centric queries.

**`ticket_id` (hash):**
- Distribution: Perfect (hash is uniform).
- Query locality: None. A query for all tickets of an event hits every shard.
- Cross-shard queries: Almost every real query is cross-shard.
- **Verdict:** Worst choice. Uniform distribution means nothing if every query is a scatter-gather.

### Recommended: Shard by `event_id`

The purchase flow — the most critical operation — is entirely shard-local:
1. Look up event → single shard
2. Check available tickets → same shard
3. Reserve ticket → same shard
4. Process payment → same shard (or a separate payment shard)
5. Create order → same shard

For cross-shard queries like "all orders for user X," maintain a secondary index or use an async process to replicate order summaries to a user-centric store.

### The Hotspot Problem: Taylor Swift Sharding

Even with a good shard key, single high-traffic events create hotspots. Imagine Taylor Swift announces a tour. Suddenly one shard handles 100x the traffic of all others.

**Strategies to handle hotspots:**

1. **Sub-sharding by ticket tier:** Split large events across multiple "virtual shards" — e.g., floor tickets on shard 0, lower bowl on shard 1, upper bowl on shard 2. Requires application-level logic.

2. **Read replica per shard:** Each shard gets its own read replicas. Ticket availability reads go to replicas; purchase writes hit the shard primary.

3. **Caching the hot event:** Cache available ticket counts in Redis. Serve reads from cache. Only hit the shard for actual purchase transactions. Reduces database load by 80-90% for read-heavy browsing during flash sales.

4. **Rate limiting at the application level:** Cap the request rate per event_id at the API gateway or edge layer. Prevent the database from being overwhelmed by giving users queue positions instead.

The right answer for TicketPulse is almost certainly option 3 (caching) combined with option 4 (rate limiting). True sub-sharding is a last resort.

### The Cross-Shard Join Problem

```sql
-- This query is impossible in a sharded system:
SELECT u.name, e.title, o.amount
FROM users u
JOIN orders o ON o.user_id = u.id
JOIN events e ON e.id = o.event_id
WHERE u.id = 'user-123';
```

If orders are sharded by `event_id` and users are in a separate database, this query requires:
1. Fetch user from user DB.
2. Fetch orders from ALL shards (or from a user-order index).
3. Fetch event details from each relevant shard.
4. Join in application code.

This is slow and complex. Strategies to mitigate:

| Strategy | How It Works | Trade-off |
|---|---|---|
| **Denormalize** | Store user name and event title in the order record | Data duplication. Must update on name changes. |
| **Secondary index** | Maintain a `user_orders` table mapping user_id → shard + order_id | Extra write on every order. Eventually consistent. |
| **CQRS read model** | Project events into a read-optimized store (Elasticsearch, materialized view) | Eventual consistency. More infrastructure. |
| **Avoid the query** | Design the UX so this query is rare | Cheapest solution if possible. |

### 🤔 Reflect: Partitioning vs Sharding

| | Partitioning | Sharding |
|---|---|---|
| **What it splits** | One table into multiple physical tables | One database into multiple databases |
| **Where it runs** | Single database server | Multiple database servers |
| **Transparency** | Transparent to application (PostgreSQL handles routing) | Application must know the sharding logic |
| **When you need it** | Large tables causing vacuum/index problems, want to archive old data | Single server cannot handle the write throughput |
| **Complexity** | Low (built into PostgreSQL) | High (routing, cross-shard queries, rebalancing) |

**Rule of thumb:** Partition first. Shard only when a single server is insufficient. Most applications at 10M-100M rows do not need sharding. They need better indexes, partitioning, and read replicas.

### Sharding Tools

If you do need sharding:

- **Citus (PostgreSQL extension):** Adds distributed table support to PostgreSQL. You define a distribution column, and Citus handles routing, parallel queries, and rebalancing. Minimal application changes.
- **Vitess (MySQL):** Created by YouTube for scaling MySQL. Handles connection pooling, query routing, and resharding. Used by Slack, Square, and GitHub.
- **Application-level sharding:** You write the routing logic. Maximum control, maximum complexity. Used by many large companies with unique requirements.

> **The bigger picture:** The shard key decision is effectively permanent. Changing it later means migrating every row in your database. Spend the time upfront to get it right.

### How Figma Shards

Figma shards their database by `file_id`. Every Figma design file is a shard key. All operations on a file — loading, editing, commenting, version history — hit a single shard. This gives perfect query locality for the most common operation (working on a file).

Cross-shard queries (list all files for a user) use a secondary index. This trade-off makes sense because users work on one file at a time (hot path) but list their files occasionally (warm path).

### 🛠️ Build: Application-Level Shard Router

<details>
<summary>💡 Hint 1: Direction</summary>
Have you considered using Citus (PostgreSQL extension) before building your own router? It handles distribution column routing, parallel queries, and rebalancing with minimal application changes.
</details>

<details>
<summary>💡 Hint 2: If You're Stuck</summary>
If you do build a custom router, the hash function must be deterministic and stable. Changing it means migrating every row. Use a consistent hashing approach (as in M65) if you anticipate adding shards later.
</details>


If you implement application-level sharding, here is a simple router pattern:

```typescript
const SHARD_COUNT = 4;

function getShardIndex(eventId: string): number {
  // Consistent hash: same event always maps to the same shard
  let hash = 0;
  for (let i = 0; i < eventId.length; i++) {
    hash = (hash * 31 + eventId.charCodeAt(i)) & 0xffffffff;
  }
  return Math.abs(hash) % SHARD_COUNT;
}

class ShardRouter {
  private shards: DatabaseClient[];

  getShardForEvent(eventId: string): DatabaseClient {
    const index = getShardIndex(eventId);
    return this.shards[index];
  }

  async getAllShards(): Promise<DatabaseClient[]> {
    // For cross-shard queries — returns ALL shards to scatter-gather
    return this.shards;
  }
}

// Usage:
const router = new ShardRouter();
const shard = router.getShardForEvent('event-abc-123');
const tickets = await shard.query(
  'SELECT * FROM tickets WHERE event_id = $1 AND status = $2',
  ['event-abc-123', 'available']
);
```

**The critical property:** `getShardIndex` must be deterministic and stable. If you change the hashing logic or the shard count, every event moves to a different shard — which means you need to migrate all data. Never change the shard count without a data migration plan.

---

## 5. Putting It Together: TicketPulse Scaling Plan

Given the current symptoms, here is the recommended sequence:

```
IMMEDIATE (Week 1-2): Optimize queries and indexes
  - Run EXPLAIN ANALYZE on the top 10 slowest queries
  - Add missing indexes (check pg_stat_user_indexes for unused indexes)
  - Move analytics queries to read replicas

SHORT-TERM (Week 2-4): Add connection pooling
  - Deploy PgBouncer in front of the primary
  - Set pool_mode = transaction
  - Monitor pg_stat_activity to confirm connection count drops

MEDIUM-TERM (Month 2): Partition the tickets table
  - Range partition by event_date (quarterly)
  - Monitor autovacuum performance improvement
  - Verify partition pruning in EXPLAIN ANALYZE output

LONG-TERM (Month 3+): Only if primary CPU > 70% peak after above steps
  - Evaluate Citus for horizontal scaling
  - Consider read replica dedicated to analytics
  - Re-evaluate at 100M+ tickets or 2,000+ writes/second
```

---

## 6. Reflect (5 minutes)

### 🤔 Questions

1. **TicketPulse currently has 50M tickets on a db.r6g.xlarge (4 vCPU, 32GB). Is it time to shard?** What would you try first?

2. **A query runs fast on a partition with 1M rows but slow on a partition with 10M rows. The partition key is the same. What could cause this?** (Hint: think about index bloat, statistics, and cache fit.)

3. **You sharded by event_id and now have a Taylor Swift event with 500K tickets on one shard. That shard is overloaded during the flash sale while other shards are idle. How do you handle this without re-sharding?**

4. **A product manager asks for a dashboard showing "total revenue by month across all events." In a sharded system, how would you implement this efficiently?**

5. **Replication lag spikes to 45 seconds during your nightly analytics job. The analytics query cannot be moved — it was added by the finance team and queries the primary directly. What are your options?**

### 🤔 Reflection Prompt

Look back at your initial hypotheses from Section 0. Which scaling technique addressed which symptom? Did anything surprise you about the order of the scaling ladder?

---

## 7. Checkpoint

After this module, you should have:

- [ ] Understanding of the scaling ladder: indexes → replicas → connection pooling → partitioning → sharding
- [ ] Query routing rules for read replicas (which queries go where, with justification)
- [ ] A partitioned tickets table using range partitioning by event_date
- [ ] Observed partition pruning in EXPLAIN ANALYZE output
- [ ] Understanding of partition pruning pitfalls (functions on partition keys break pruning)
- [ ] PgBouncer configuration for connection multiplexing
- [ ] Understanding of instant partition detach for archiving old data
- [ ] A justified shard key choice for TicketPulse (event_id)
- [ ] Analysis of the cross-shard join problem and mitigation strategies
- [ ] Understanding of hotspot handling for high-traffic events
- [ ] Understanding of when partitioning is sufficient vs when sharding is necessary

---


> **What did you notice?** Consider how this connects to systems you've worked on. Where have you seen similar patterns — or missed opportunities to apply them?

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **Read replicas** | Multiply read capacity. Route writes to primary, reads to replicas. Manage replication lag with read-your-writes and lag-aware routing. |
| **Replication lag** | The silent danger. Monitor it. Exclude lagging replicas from transactional reads. Never run analytics on replicas serving live traffic. |
| **Connection pooling** | PgBouncer multiplexes app connections into fewer server connections. Use transaction mode. Size pools based on backend thread count, not frontend connection count. |
| **Table partitioning** | Split one table into physical sub-tables. Enables partition pruning, instant archival, and smaller indexes. Built into PostgreSQL. |
| **Partition pruning** | PostgreSQL skips partitions that cannot contain matching rows. Functions on the partition key break pruning — filter directly. |
| **Sharding** | Split data across multiple database servers. Required when a single server cannot handle write throughput. |
| **Shard key selection** | The most critical decision. Optimize for query locality on the hot path. Accept cross-shard queries on the cold path. |
| **Hotspot handling** | Cache hot events in Redis, rate-limit at the edge, and add per-shard read replicas before considering sub-sharding. |
| **Cross-shard joins** | Impossible in SQL. Mitigate with denormalization, secondary indexes, CQRS, or UX design. |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Read replica** | A copy of the primary database that serves read queries. Updated via asynchronous replication. |
| **Replication lag** | The delay between a write on the primary and that write appearing on a replica. Measured in seconds or bytes. |
| **PgBouncer** | A connection pooler for PostgreSQL that multiplexes many application connections into fewer database server connections. |
| **Partitioning** | Dividing a table into smaller physical tables (partitions) based on a column value. Managed by the database engine. |
| **Partition pruning** | The database optimizer's ability to skip partitions that cannot contain relevant rows for a query. |
| **Sharding** | Distributing data across multiple independent database servers based on a shard key. |
| **Shard key** | The column used to determine which shard stores a row. Also called distribution key or partition key (in distributed DBs). |
| **Cross-shard query** | A query that must access data from multiple shards. Typically slower and more complex than single-shard queries. |
| **Citus** | A PostgreSQL extension that adds distributed table support, enabling horizontal scaling without leaving the PostgreSQL ecosystem. |
| **Hotspot** | A shard or partition that receives disproportionate traffic, becoming a bottleneck while others remain underutilized. |

---

## Further Reading

- Martin Kleppmann, *Designing Data-Intensive Applications*, Chapter 6 (Partitioning) — the canonical reference on sharding strategies
- **Chapter 24 of the 100x Engineer Guide**: PostgreSQL internals — MVCC, WAL, vacuum mechanics, and the query planner
- [PostgreSQL Partitioning Documentation](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [Figma's Database Scaling Story](https://www.figma.com/blog/how-figma-scaled-to-multiple-databases/) — practical sharding decisions
- [Citus Documentation](https://docs.citusdata.com/) — distributed PostgreSQL
- [PgBouncer Documentation](https://www.pgbouncer.org/config.html) — connection pooling configuration reference

---

## What's Next

Next up: **[L3-M64: CDN & Edge Computing](L3-M64-cdn-and-edge-computing.md)** -- you will push TicketPulse's content and logic to the network edge, learning to serve 80% of traffic without hitting your origin servers.
