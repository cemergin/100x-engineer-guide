# L1-M07: Indexing & Query Performance
> ⏱️ 60 min | 🟢 Core | Prerequisites: L1-M05, L1-M06
> Source: Chapters 2 & 24 of the 100x Engineer Guide

## What You'll Learn
- How to read EXPLAIN ANALYZE output line by line
- What a sequential scan is and why it kills performance at scale
- How B-tree indexes work and why they speed up lookups
- Composite indexes and why column order matters
- Partial indexes, covering indexes, and expression indexes
- How to identify and remove unused indexes
- The write penalty of over-indexing

## Why This Matters
A missing index is the #1 cause of slow database queries in production. A single index can turn a query from 30 seconds to 3 milliseconds — a 10,000x improvement. But blindly adding indexes makes writes slower and wastes disk space. This module teaches you to think like a database, diagnose slow queries, and add exactly the right indexes.

## Prereq Check

Connect to TicketPulse with data from M05:

```bash
docker exec -it ticketpulse-postgres psql -U ticketpulse
```

First, let's generate more data so performance differences are visible. 120 tickets isn't enough to see index benefits — we need tens of thousands of rows.

```sql
-- Generate 100,000 tickets across our events
-- (This replaces the small dataset from M05 for performance testing)
TRUNCATE tickets CASCADE;
TRUNCATE order_items CASCADE;

INSERT INTO tickets (event_id, section, row, seat, price, status)
SELECT
    (s % 6) + 1 AS event_id,
    CASE (s % 5)
        WHEN 0 THEN 'Floor'
        WHEN 1 THEN 'Lower Bowl'
        WHEN 2 THEN 'Upper Bowl'
        WHEN 3 THEN 'Mezzanine'
        WHEN 4 THEN 'Balcony'
    END,
    'R' || ((s / 20) + 1),
    'S' || ((s % 20) + 1),
    CASE (s % 5)
        WHEN 0 THEN 250.00
        WHEN 1 THEN 150.00
        WHEN 2 THEN 95.00
        WHEN 3 THEN 75.00
        WHEN 4 THEN 45.00
    END,
    CASE
        WHEN random() < 0.6 THEN 'sold'
        WHEN random() < 0.8 THEN 'available'
        WHEN random() < 0.95 THEN 'reserved'
        ELSE 'cancelled'
    END
FROM generate_series(0, 99999) AS s;

-- Verify
SELECT COUNT(*) FROM tickets;
-- Should return 100,000

-- Update statistics so the planner has accurate info
ANALYZE tickets;
```

---

## Part 1: The Slow Query (5 min)

### 🔍 Try It Now

Let's run a query that TicketPulse would run on every page load — finding available tickets for an event with a price filter:

```sql
-- Turn on timing
\timing on

-- Find available tickets for event 1, priced under $100
SELECT id, section, row, seat, price
FROM tickets
WHERE event_id = 1
  AND status = 'available'
  AND price < 100.00
ORDER BY price, section;
```

On 100K rows, this might feel instant. But let's see what the database actually did.

---

## Part 2: EXPLAIN ANALYZE — Reading the Execution Plan (15 min)

### 🔍 Try It Now

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id, section, row, seat, price
FROM tickets
WHERE event_id = 1
  AND status = 'available'
  AND price < 100.00
ORDER BY price, section;
```

You should see something like:

```
Sort  (cost=2100.50..2101.25 rows=300 width=52)
      (actual time=25.1..25.2 rows=287 loops=1)
  Sort Key: price, section
  Sort Method: quicksort  Memory: 48kB
  Buffers: shared hit=834
  ->  Seq Scan on tickets  (cost=0.00..2089.00 rows=300 width=52)
                            (actual time=0.03..24.8 rows=287 loops=1)
        Filter: ((event_id = 1) AND (status = 'available') AND (price < 100.00))
        Rows Removed by Filter: 99713
        Buffers: shared hit=834
Planning Time: 0.15 ms
Execution Time: 25.3 ms
```

### Reading This Line by Line

Read EXPLAIN output **bottom-up** (innermost to outermost):

**Line: `Seq Scan on tickets`**
- **Seq Scan** = Sequential Scan = reading EVERY row in the table
- The database read all 100,000 rows just to find 287 matching ones
- `Rows Removed by Filter: 99713` — it threw away 99.7% of what it read

**Line: `Buffers: shared hit=834`**
- It read 834 pages (834 * 8 KB = ~6.5 MB of data)
- `shared hit` means the pages were in memory (buffer cache). If it said `shared read`, those pages came from disk — much slower.

**Line: `Sort`**
- After finding the 287 rows, it sorted them by price and section
- `quicksort Memory: 48kB` — the sort fit in memory (good)

**Line: `cost=0.00..2089.00`**
- These are the planner's **estimated** costs (not milliseconds). Lower is better. The first number is startup cost, the second is total cost.

**Line: `actual time=0.03..24.8`**
- The **actual** time in milliseconds. Startup took 0.03ms, full execution took 24.8ms.
- Compare estimated rows (300) vs actual rows (287) — close enough. If these differ wildly, your statistics are stale (run `ANALYZE`).

### 💡 Insight: Why Seq Scan is Bad at Scale

With 100K rows, reading 834 pages takes ~25ms. That seems fine. But consider:
- With 10M rows: 83,400 pages = ~650 MB = **2.5 seconds**
- With 100M rows: **25 seconds**
- Under load (100 concurrent users): 100 * 25 seconds of I/O = your database melts

Sequential scans scale linearly with table size. Indexes give you logarithmic scaling.

---

## Part 3: Add an Index — See the Difference (10 min)

### 🔍 Try It Now

```sql
-- Create an index on the columns we filter by
CREATE INDEX idx_tickets_event_status_price ON tickets (event_id, status, price);

-- Run the SAME query again
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id, section, row, seat, price
FROM tickets
WHERE event_id = 1
  AND status = 'available'
  AND price < 100.00
ORDER BY price, section;
```

New output:

```
Sort  (cost=25.50..26.25 rows=300 width=52)
      (actual time=0.4..0.5 rows=287 loops=1)
  Sort Key: price, section
  Sort Method: quicksort  Memory: 48kB
  Buffers: shared hit=12
  ->  Index Scan using idx_tickets_event_status_price on tickets
          (cost=0.42..14.50 rows=300 width=52)
          (actual time=0.05..0.3 rows=287 loops=1)
        Index Cond: ((event_id = 1) AND (status = 'available') AND (price < 100.00))
        Buffers: shared hit=12
Planning Time: 0.3 ms
Execution Time: 0.6 ms
```

**The results:**

| Metric | Before (Seq Scan) | After (Index Scan) | Improvement |
|--------|-------------------|-------------------|-------------|
| Execution time | 25.3 ms | 0.6 ms | **42x faster** |
| Pages read | 834 | 12 | **70x fewer** |
| Rows examined | 100,000 | 287 | **348x fewer** |

The index let Postgres jump directly to the 287 matching rows instead of reading all 100,000.

---

## Part 4: How B-Tree Indexes Work (10 min)

A B-tree (balanced tree) index is a sorted data structure that allows Postgres to find rows in O(log N) time instead of O(N).

### Conceptual Structure

```
                        [50000]
                       /        \
              [25000]              [75000]
             /       \            /       \
      [12500]   [37500]   [62500]   [87500]
       / \       / \       / \       / \
     ... ...   ... ...   ... ...   ... ...

     Leaf nodes: [ticket_id=1, ctid=(0,1)] [ticket_id=2, ctid=(0,2)] ...
```

For our composite index on `(event_id, status, price)`:

```
Root: event_id boundaries
  └── event_id=1
       └── status='available'
            └── price < 100: directly to these leaf entries
            └── price >= 100: skip these entirely
       └── status='sold': skip entirely
  └── event_id=2: skip entirely (we only want event_id=1)
```

The index is sorted by `event_id`, then by `status` within each `event_id`, then by `price` within each `(event_id, status)`. This is why column order matters.

### 🤔 Reflect: Column Order

Our index is `(event_id, status, price)`. Think about what happens with these queries:

```sql
-- Query A: WHERE event_id = 1
-- Can use the index? YES — event_id is the leftmost column

-- Query B: WHERE status = 'available'
-- Can use the index? NO — status is not leftmost, can't skip event_id

-- Query C: WHERE event_id = 1 AND price < 100
-- Can use the index? PARTIALLY — uses event_id, but price has a gap (status is between them)

-- Query D: WHERE price < 100
-- Can use the index? NO — price is the last column, can't skip the first two
```

This is the **leftmost prefix rule**: a composite index on `(a, b, c)` can serve queries on `a`, `(a, b)`, or `(a, b, c)` — but NOT `b`, `c`, `(b, c)`, or `(a, c)` efficiently.

### 🔍 Try It Now: Prove It

```sql
-- This uses the index (starts with event_id)
EXPLAIN (ANALYZE) SELECT * FROM tickets WHERE event_id = 3;

-- This does NOT use the index (starts with status, skipping event_id)
EXPLAIN (ANALYZE) SELECT * FROM tickets WHERE status = 'available';

-- This partially uses the index
EXPLAIN (ANALYZE) SELECT * FROM tickets WHERE event_id = 1 AND price < 100;
```

---

## Part 5: Composite Index Column Ordering Strategy (5 min)

**The rule for ordering columns in a composite index:**

1. **Equality columns first** — columns compared with `=`
2. **Range columns last** — columns compared with `<`, `>`, `BETWEEN`, `LIKE 'prefix%'`
3. Among equality columns, put the most selective (highest cardinality) first

### 🔍 Try It Now

```sql
-- Query pattern: WHERE event_id = ? AND status = ? AND price BETWEEN ? AND ?
-- Optimal index:
-- CREATE INDEX ON tickets (event_id, status, price);
--                          ↑ equality  ↑ equality  ↑ range

-- WRONG order would be:
-- CREATE INDEX ON tickets (price, event_id, status);
-- This puts the range column first — the index can only use price for the range
-- then has to scan all matching prices to filter event_id and status
```

### ⚠️ Common Mistake: Redundant Indexes

```sql
-- If you have:
CREATE INDEX idx_a ON tickets (event_id, status, price);

-- You do NOT also need:
CREATE INDEX idx_b ON tickets (event_id);          -- redundant! idx_a covers this
CREATE INDEX idx_c ON tickets (event_id, status);   -- redundant! idx_a covers this

-- But you DO need a separate index for:
CREATE INDEX idx_d ON tickets (status);             -- idx_a can't serve status-only queries
```

---

## Part 6: Advanced Index Types (10 min)

### Covering Indexes (Index-Only Scans)

A covering index includes all columns the query needs, so Postgres never touches the heap:

```sql
-- This query needs: id, price (from WHERE and SELECT)
-- Our current index has (event_id, status, price) but not section, row, seat

-- Create a covering index
CREATE INDEX idx_tickets_covering ON tickets (event_id, status, price)
    INCLUDE (section, row, seat);

EXPLAIN (ANALYZE, BUFFERS)
SELECT id, section, row, seat, price
FROM tickets
WHERE event_id = 1 AND status = 'available' AND price < 100
ORDER BY price;
```

Look for **"Index Only Scan"** in the output — this means zero heap access.

### Partial Indexes

Index only the rows that matter:

```sql
-- Most queries filter for available tickets. Only 20% of tickets are available.
-- Why index all 100K rows when we only query 20K?
CREATE INDEX idx_tickets_available
    ON tickets (event_id, price)
    WHERE status = 'available';

EXPLAIN (ANALYZE)
SELECT * FROM tickets
WHERE status = 'available' AND event_id = 2 AND price < 150;
```

The partial index is smaller (fewer entries = less memory, faster scans) and only maintained when rows match the WHERE clause.

### Expression Indexes

```sql
-- If you query by lowercase section name:
CREATE INDEX idx_tickets_section_lower ON tickets (LOWER(section));

EXPLAIN (ANALYZE)
SELECT * FROM tickets WHERE LOWER(section) = 'floor';
```

Without the expression index, Postgres cannot use any index because `LOWER()` transforms the column value.

---

## Part 7: Design Optimal Indexes for TicketPulse (5 min)

### 🛠️ Your Turn

TicketPulse runs these 5 queries most frequently. Design the optimal set of indexes. Think about which indexes overlap and which are truly needed.

1. **Event page**: `WHERE event_id = ? AND status = 'available' ORDER BY price`
2. **Customer orders**: `WHERE customer_email = ? ORDER BY ordered_at DESC` (on orders table)
3. **Admin search**: `WHERE event_date BETWEEN ? AND ? AND status = ?` (on events table)
4. **Revenue report**: `WHERE status = 'sold' GROUP BY event_id` (on tickets table)
5. **Venue listing**: `WHERE venue_id = ? ORDER BY event_date` (on events table)

<details>
<summary>Solution</summary>

```sql
-- 1. Event page (most critical — user-facing, high frequency)
CREATE INDEX idx_tickets_event_available ON tickets (event_id, price)
    WHERE status = 'available';
-- Partial index: only indexes available tickets. Covers the ORDER BY price.

-- 2. Customer order lookup
CREATE INDEX idx_orders_customer ON orders (customer_email, ordered_at DESC);

-- 3. Admin event search
CREATE INDEX idx_events_date_status ON events (status, event_date);
-- status (equality) first, event_date (range) second

-- 4. Revenue report — sold tickets grouped by event
CREATE INDEX idx_tickets_sold_event ON tickets (event_id)
    WHERE status = 'sold';
-- Partial index on sold tickets only

-- 5. Venue event listing
CREATE INDEX idx_events_venue_date ON events (venue_id, event_date);

-- Total: 5 indexes for 5 query patterns. No redundancy.
```

</details>

---

## Part 8: The Write Penalty and Index Monitoring (5 min)

### ⚠️ Common Mistake: Over-Indexing

Every index you add:
- Slows down INSERT (must update every index)
- Slows down UPDATE (if indexed columns change)
- Slows down DELETE (must update every index)
- Uses disk space (sometimes as much as the table itself)

### 🔍 Try It Now: Measure the Write Penalty

```sql
\timing on

-- Insert 10,000 rows WITHOUT extra indexes (drop them first)
DROP INDEX IF EXISTS idx_tickets_event_status_price;
DROP INDEX IF EXISTS idx_tickets_covering;
DROP INDEX IF EXISTS idx_tickets_available;
DROP INDEX IF EXISTS idx_tickets_section_lower;
DROP INDEX IF EXISTS idx_tickets_event_available;
DROP INDEX IF EXISTS idx_tickets_sold_event;

INSERT INTO tickets (event_id, section, row, seat, price, status)
SELECT (s % 6) + 1, 'Test', 'R1', 'S' || s, 50.00, 'available'
FROM generate_series(1, 10000) AS s;
-- Note the time

-- Now add 5 indexes
CREATE INDEX idx_t1 ON tickets (event_id, status, price);
CREATE INDEX idx_t2 ON tickets (status, event_id);
CREATE INDEX idx_t3 ON tickets (price);
CREATE INDEX idx_t4 ON tickets (section, row);
CREATE INDEX idx_t5 ON tickets (created_at);

-- Insert another 10,000 rows WITH 5 indexes
INSERT INTO tickets (event_id, section, row, seat, price, status)
SELECT (s % 6) + 1, 'Test2', 'R1', 'S' || s, 50.00, 'available'
FROM generate_series(1, 10000) AS s;
-- Note the time — it will be slower
```

### 📊 Observe: Which Indexes Are Actually Used?

```sql
-- Check index usage statistics
SELECT indexrelname AS index_name,
       idx_scan AS times_used,
       idx_tup_read AS rows_read,
       idx_tup_fetch AS rows_fetched,
       pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

Any index with `idx_scan = 0` is a candidate for removal — it costs write performance but provides zero read benefit.

```sql
-- Clean up our test indexes
DROP INDEX idx_t1, idx_t2, idx_t3, idx_t4, idx_t5;

-- Remove test data
DELETE FROM tickets WHERE section IN ('Test', 'Test2');
ANALYZE tickets;
```

---

## 🏁 Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **EXPLAIN ANALYZE** | Always read it bottom-up. Look at actual vs estimated rows, buffer hits vs reads. |
| **Seq Scan** | Reads every row. Fine for small tables, catastrophic for large ones. |
| **B-tree index** | Sorted structure. O(log N) lookups instead of O(N). Default index type. |
| **Composite index** | Column order matters. Equality first, range last. Leftmost prefix rule. |
| **Partial index** | Index only the rows you query. Smaller, faster, less write overhead. |
| **Covering index** | Include all needed columns to enable Index Only Scans (zero heap access). |
| **Over-indexing** | Each index slows writes. Monitor `pg_stat_user_indexes` and drop unused indexes. |

**The optimization process:**
1. Identify the slow query
2. Run `EXPLAIN (ANALYZE, BUFFERS)`
3. Look for Seq Scans on large tables
4. Design an index that matches the WHERE clause columns (equality first, range last)
5. Re-run EXPLAIN to confirm the index is used
6. Monitor with `pg_stat_user_indexes`

## What's Next

In **L1-M08: Data Modeling Decisions**, you'll learn when to normalize, when to denormalize, and how to design schemas that perform well under real-world access patterns.

## 📚 Further Reading
- [Use The Index, Luke](https://use-the-index-luke.com/) — The best free resource on SQL indexing
- [PostgreSQL EXPLAIN Documentation](https://www.postgresql.org/docs/current/using-explain.html)
- Chapter 24 of the 100x Engineer Guide: Section 4 — Query Optimization Masterclass
- [pgMustard](https://www.pgmustard.com/) — Visual EXPLAIN ANALYZE tool
- [explain.depesz.com](https://explain.depesz.com/) — Paste your EXPLAIN output for analysis
