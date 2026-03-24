# L3-M63: Database at Scale

> **Loop 3 (Mastery)** | Section 3A: Global Scale Architecture | ⏱️ 75 min | 🟡 Deep Dive | Prerequisites: L2-M37 (PostgreSQL Internals), L2-M35 (Database Per Service), L3-M61 (Multi-Region Design)
>
> **Source:** Chapters 1, 19, 31, 22, 23 of the 100x Engineer Guide

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

---

## 1. Read Replicas (15 minutes)

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

### Replication Lag Management

The danger of read replicas is replication lag. During peak write load, replicas can fall behind. A user places an order, refreshes, and their order is not there yet (because they hit a replica that has not received the write).

**Strategies:**

1. **Read-your-writes consistency:** After a write, route the user's subsequent reads to the primary for a short window (e.g., 5 seconds). Implement via a session flag or sticky routing.

2. **Monitoring replication lag:**
   ```sql
   -- On the replica:
   SELECT
     now() - pg_last_xact_replay_timestamp() AS replication_lag;

   -- Alert if lag exceeds 5 seconds
   ```

3. **Lag-aware routing:** If a replica's lag exceeds a threshold, stop sending it traffic until it catches up.

---

## 2. Table Partitioning (20 minutes)

### The Problem with One Big Table

The tickets table has 50 million rows. Even with indexes, certain operations suffer:
- **Vacuum and autovacuum** must process the entire table. This causes I/O spikes.
- **Index bloat** — indexes grow large and less cache-friendly.
- **Bulk operations** (deleting old data) require scanning massive indexes.
- **Sequential scans** for queries that hit too many rows for an index to help.

Partitioning splits one logical table into multiple physical tables (partitions). Each partition is an independent table with its own indexes and storage. PostgreSQL routes queries to the relevant partition(s) automatically.

### 🛠️ Build: Partition the Tickets Table

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

---

## 3. Sharding (25 minutes)

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
| **Transparancy** | Transparent to application (PostgreSQL handles routing) | Application must know the sharding logic |
| **When you need it** | Large tables causing vacuum/index problems, want to archive old data | Single server cannot handle the write throughput |
| **Complexity** | Low (built into PostgreSQL) | High (routing, cross-shard queries, rebalancing) |

**Rule of thumb:** Partition first. Shard only when a single server is insufficient. Most applications at 10M-100M rows do not need sharding. They need better indexes, partitioning, and read replicas.

### Sharding Tools

If you do need sharding:

- **Citus (PostgreSQL extension):** Adds distributed table support to PostgreSQL. You define a distribution column, and Citus handles routing, parallel queries, and rebalancing. Minimal application changes.
- **Vitess (MySQL):** Created by YouTube for scaling MySQL. Handles connection pooling, query routing, and resharding. Used by Slack, Square, and GitHub.
- **Application-level sharding:** You write the routing logic. Maximum control, maximum complexity. Used by many large companies with unique requirements.

### 💡 Insight: How Figma Shards

Figma shards their database by `file_id`. Every Figma design file is a shard key. All operations on a file — loading, editing, commenting, version history — hit a single shard. This gives perfect query locality for the most common operation (working on a file).

Cross-shard queries (list all files for a user) use a secondary index. This trade-off makes sense because users work on one file at a time (hot path) but list their files occasionally (warm path).

---

## 4. Reflect (5 minutes)

### 🤔 Questions

1. **TicketPulse currently has 50M tickets on a db.r6g.xlarge (4 vCPU, 32GB). Is it time to shard?** What would you try first?

2. **A query runs fast on a partition with 1M rows but slow on a partition with 10M rows. The partition key is the same. What could cause this?** (Hint: think about index bloat, statistics, and cache fit.)

3. **You sharded by event_id and now have a Taylor Swift event with 500K tickets on one shard. That shard is overloaded during the flash sale while other shards are idle. How do you handle this?**

4. **A product manager asks for a dashboard showing "total revenue by month across all events." In a sharded system, how would you implement this efficiently?**

---

## 5. Checkpoint

After this module, you should have:

- [ ] Understanding of the scaling ladder: indexes → replicas → partitioning → sharding
- [ ] Query routing rules for read replicas (which queries go where, with justification)
- [ ] A partitioned tickets table using range partitioning by event_date
- [ ] Observed partition pruning in EXPLAIN ANALYZE output
- [ ] Understanding of instant partition detach for archiving old data
- [ ] A justified shard key choice for TicketPulse (event_id)
- [ ] Analysis of the cross-shard join problem and mitigation strategies
- [ ] Understanding of when partitioning is sufficient vs when sharding is necessary

---

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **Read replicas** | Multiply read capacity. Route writes to primary, reads to replicas. Manage replication lag with read-your-writes. |
| **Table partitioning** | Split one table into physical sub-tables. Enables partition pruning, instant archival, and smaller indexes. Built into PostgreSQL. |
| **Partition pruning** | PostgreSQL skips partitions that cannot contain matching rows. Turns a 50M row scan into a 5M row scan. |
| **Sharding** | Split data across multiple database servers. Required when a single server cannot handle write throughput. |
| **Shard key selection** | The most critical decision. Optimize for query locality on the hot path. Accept cross-shard queries on the cold path. |
| **Cross-shard joins** | Impossible in SQL. Mitigate with denormalization, secondary indexes, CQRS, or UX design. |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Read replica** | A copy of the primary database that serves read queries. Updated via asynchronous replication. |
| **Partitioning** | Dividing a table into smaller physical tables (partitions) based on a column value. Managed by the database engine. |
| **Partition pruning** | The database optimizer's ability to skip partitions that cannot contain relevant rows for a query. |
| **Sharding** | Distributing data across multiple independent database servers based on a shard key. |
| **Shard key** | The column used to determine which shard stores a row. Also called distribution key or partition key (in distributed DBs). |
| **Cross-shard query** | A query that must access data from multiple shards. Typically slower and more complex than single-shard queries. |
| **Citus** | A PostgreSQL extension that adds distributed table support, enabling horizontal scaling without leaving the PostgreSQL ecosystem. |

---

## Further Reading

- Martin Kleppmann, *Designing Data-Intensive Applications*, Chapter 6 (Partitioning)
- [PostgreSQL Partitioning Documentation](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [Figma's Database Scaling Story](https://www.figma.com/blog/how-figma-scaled-to-multiple-databases/) — practical sharding decisions
- [Citus Documentation](https://docs.citusdata.com/) — distributed PostgreSQL
- Chapter 1 of the 100x Engineer Guide: Section 2.2 (Sharding Strategies)
