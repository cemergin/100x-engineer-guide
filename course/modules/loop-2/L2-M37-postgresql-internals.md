# L2-M37: PostgreSQL Internals

> **Loop 2 (Practice)** | Section 2B: Performance & Databases | ⏱️ 75 min | 🟡 Deep Dive | Prerequisites: L1-M05, L1-M07, L2-M31
>
> **Source:** Chapter 24 of the 100x Engineer Guide

## What You'll Learn
- How MVCC works under the hood — xmin, xmax, and tuple versioning
- What the Write-Ahead Log (WAL) is and why it guarantees crash recovery
- Why dead tuples accumulate and how VACUUM reclaims space
- Transaction ID wraparound: the silent killer that can freeze your database
- Buffer pool mechanics and the double-buffering problem
- How to tune these internals for TicketPulse's high-churn workload

## Why This Matters
TicketPulse's tickets table is one of the highest-churn tables you'll encounter — tickets are created, reserved, sold, expired, and cancelled constantly. Every UPDATE creates a dead tuple. Every transaction consumes a transaction ID. If you don't understand the machinery underneath, your database will bloat, slow down, and eventually stop accepting writes. This module gives you the mental model to prevent all of that.

## Prereq Check

You should have the TicketPulse microservices running from Section 2A with separate databases per service. For this module, we'll work directly with the ticket-service database.

```bash
# Connect to the ticket service database
docker exec -it ticketpulse-ticket-db psql -U ticketpulse -d tickets

# Verify you have data
SELECT COUNT(*) FROM tickets;
-- You should have data from previous modules
```

If you need test data, generate it:

```sql
-- Generate 100K tickets for performance testing
INSERT INTO tickets (event_id, section, row_num, seat, price, status, created_at, updated_at)
SELECT
    (s % 20) + 1 AS event_id,
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
        WHEN random() < 0.3 THEN 'available'
        WHEN random() < 0.7 THEN 'sold'
        WHEN random() < 0.85 THEN 'reserved'
        WHEN random() < 0.95 THEN 'expired'
        ELSE 'cancelled'
    END,
    NOW() - (random() * INTERVAL '90 days'),
    NOW() - (random() * INTERVAL '30 days')
FROM generate_series(0, 99999) AS s;

ANALYZE tickets;
```

---

## Part 1: MVCC — Multi-Version Concurrency Control (20 min)

### The Core Idea

When two users try to buy the same ticket simultaneously, what happens? In a naive database, you'd lock the row — one user waits while the other finishes. PostgreSQL takes a different approach: it keeps **multiple versions** of each row so readers never block writers and writers never block readers.

Every row in PostgreSQL carries hidden system columns that track its lifecycle:

| Column | Meaning |
|--------|---------|
| `xmin` | Transaction ID that **created** this tuple |
| `xmax` | Transaction ID that **deleted or updated** this tuple (0 if still live) |
| `cmin` | Command counter within the inserting transaction |
| `cmax` | Command counter within the deleting transaction |
| `ctid` | Physical location: `(page_number, item_number)` |

### 🔍 Try It: See the Hidden Columns

```sql
-- You can actually query these hidden columns
SELECT xmin, xmax, ctid, id, status, price
FROM tickets
LIMIT 10;
```

You'll see something like:

```
 xmin  | xmax | ctid    | id |  status   | price
-------+------+---------+----+-----------+--------
 12045 |    0 | (0,1)   |  1 | available | 250.00
 12045 |    0 | (0,2)   |  2 | sold      | 150.00
 12045 |    0 | (0,3)   |  3 | reserved  |  95.00
```

- `xmin = 12045`: All three rows were created by transaction 12045 (our bulk insert)
- `xmax = 0`: No transaction has deleted or updated these rows yet
- `ctid = (0,1)`: Row is at page 0, item 1

### 🔍 Try It: Watch MVCC in Action — Two Concurrent Updates

Open **two separate psql sessions** (two terminal windows). We'll simulate two customers trying to buy the same ticket.

**Session A:**
```sql
-- Find an available ticket
SELECT id, status, price FROM tickets WHERE status = 'available' LIMIT 1;
-- Note the ID. Let's say it's 42.

BEGIN;
UPDATE tickets SET status = 'reserved' WHERE id = 42;
-- DON'T COMMIT YET. Check what happened:
SELECT xmin, xmax, ctid, id, status FROM tickets WHERE id = 42;
```

**Session B (while A is still open):**
```sql
-- What does Session B see?
SELECT id, status FROM tickets WHERE id = 42;
-- It still sees 'available'! Session A hasn't committed.

-- Now try to update the same row:
BEGIN;
UPDATE tickets SET status = 'reserved' WHERE id = 42;
-- This BLOCKS. Session B is waiting for Session A to commit or rollback.
```

**Back to Session A:**
```sql
COMMIT;
-- Session B's UPDATE now executes — but it updates the already-reserved ticket
```

**Session B (now unblocked):**
```sql
-- Check the result
SELECT id, status FROM tickets WHERE id = 42;
-- status = 'reserved' (Session B's update ran on top of A's committed version)
ROLLBACK;
```

### How UPDATE Actually Works

When you UPDATE a row, Postgres does NOT modify it in place. Instead:

1. The old tuple gets its `xmax` set to the current transaction ID (marking it as "dead after this transaction")
2. A **brand new tuple** is inserted with `xmin` = current transaction ID
3. The old tuple's `ctid` is updated to point to the new tuple (version chain)

This means **every UPDATE is essentially a DELETE + INSERT**. This has major implications:
- Updates are more expensive than you might expect
- Dead tuples accumulate (the old versions stick around)
- Indexes must be updated even if the indexed column didn't change (HOT updates are an exception — more on this later)

### 🔍 Try It: Prove UPDATE Creates a New Tuple

```sql
-- Check current state
SELECT xmin, xmax, ctid, id, status FROM tickets WHERE id = 1;
-- Example: xmin=12045, xmax=0, ctid=(0,1)

-- Update it
UPDATE tickets SET status = 'sold' WHERE id = 1;

-- Check again
SELECT xmin, xmax, ctid, id, status FROM tickets WHERE id = 1;
-- New xmin (your current transaction ID), xmax=0, ctid might have CHANGED
-- The row moved — it's a new tuple!
```

### The Visibility Check

Every time Postgres reads a tuple, it runs a visibility check:

```
A tuple is VISIBLE to transaction T if:
  1. xmin is committed AND was committed before T's snapshot
  2. AND (xmax = 0                          -- tuple is live
         OR xmax is aborted                  -- deleter rolled back
         OR xmax is not visible to T)        -- deleter hasn't committed from T's view
```

This check runs for **every single tuple** your query touches. It's cheap but not free.

### 🤔 Think About It

TicketPulse updates tickets frequently: available -> reserved -> sold, or available -> reserved -> expired -> available again. Each state change creates a new tuple version.

> **Question**: If a ticket goes through 5 status changes, how many tuple versions exist in the table? What happens to the old ones?
>
> Think about this before moving on. We'll answer it in Part 3 (Vacuum).

---

> **Before you continue:** When you run `UPDATE tickets SET status = 'sold' WHERE id = 42`, does PostgreSQL modify the row in place? Or does something more interesting happen? Write down your mental model before reading on.


## Part 2: WAL — The Write-Ahead Log (15 min)

### The Durability Guarantee

The Write-Ahead Log answers a critical question: if the server crashes mid-transaction, how does Postgres recover without losing committed data?

The rule is simple: **before any change is written to the actual data files, a record of that change must first be written to the WAL and flushed to disk.**

### How the Write Path Works

```
1. Your SQL: UPDATE tickets SET status = 'sold' WHERE id = 42;

2. Postgres modifies the page in shared_buffers (memory only)

3. Postgres writes a WAL record describing the change to the WAL buffer (memory)

4. On COMMIT: WAL buffer → WAL file on disk (fsync)

5. Returns "COMMIT" to your application
   ↓
   ... time passes ...
   ↓
6. Background: checkpointer writes dirty pages from shared_buffers → data files
```

Key insight: your data files are **always behind** the WAL. The WAL is the source of truth. If the server crashes after step 4 but before step 6, Postgres replays the WAL on startup and reapplies the changes.

### Why Sequential Writes Matter

WAL converts random writes (updating arbitrary pages scattered across the heap) into **sequential writes** (appending to the WAL). Sequential I/O is dramatically faster than random I/O on both spinning disks and SSDs.

### 🔍 Try It: Watch the WAL Advance

```sql
-- Check current WAL position
SELECT pg_current_wal_lsn();
-- Example: 0/1A3B4C0

-- Make some changes
UPDATE tickets SET price = price + 1 WHERE event_id = 1;

-- Check again
SELECT pg_current_wal_lsn();
-- Example: 0/1A5D890 — it advanced!

-- How much WAL has been generated?
SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), '0/1A3B4C0') AS bytes_written;
```

### 🔍 Try It: WAL Generation Rate

```sql
-- See how much WAL you generate with a bulk update
SELECT pg_current_wal_lsn() AS before;

UPDATE tickets SET updated_at = NOW() WHERE status = 'sold';

SELECT pg_current_wal_lsn() AS after;

-- Calculate the difference
SELECT pg_size_pretty(
    pg_wal_lsn_diff(
        pg_current_wal_lsn(),
        '<paste the before value here>'::pg_lsn
    )
) AS wal_generated;
```

Updating thousands of rows generates megabytes of WAL. This matters for:
- **Replication lag**: Replicas must replay all this WAL
- **Disk usage**: WAL segments accumulate until checkpointed
- **Backup size**: PITR backups include all WAL segments

### Checkpoint: When Dirty Pages Hit Disk

A **checkpoint** is when Postgres writes all dirty (modified) pages from shared buffers to their data files on disk. After a checkpoint, the WAL records before it are no longer needed for crash recovery.

```
Key checkpoint settings:
  checkpoint_timeout = 5min      -- Max time between checkpoints
  max_wal_size = 1GB             -- Triggers checkpoint when WAL grows this large
  checkpoint_completion_target = 0.9  -- Spread I/O over 90% of the interval
```

**Checkpoint storms**: If your write rate is very high, checkpoints happen frequently and the checkpointer must flush many dirty pages at once, causing I/O spikes. You'll feel this as periodic latency spikes in TicketPulse.

### synchronous_commit: The Speed vs Safety Tradeoff

```sql
-- Default: wait for WAL flush before returning COMMIT (safest)
SET synchronous_commit = on;

-- Faster: return COMMIT before WAL flush (risk: lose last ~600ms of commits on crash)
SET synchronous_commit = off;
```

> **When would you use `synchronous_commit = off`?** Think about which TicketPulse operations could tolerate losing the last half-second of data versus which absolutely cannot. A ticket purchase? Never. An analytics event log? Maybe.

---

> **Before you continue:** If a ticket goes through 5 status changes (available, reserved, sold, refunded, re-listed), how many row versions exist in the table? What happens to the old ones?


## Part 3: Vacuum — Cleaning Up Dead Tuples (20 min)

### The Problem

Remember from Part 1: every UPDATE creates a dead tuple. Every DELETE creates a dead tuple. These dead tuples still occupy space on disk.

For TicketPulse's tickets table:
- A ticket goes available -> reserved -> sold: **2 dead tuples** per ticket
- A ticket goes available -> reserved -> expired -> available: **3 dead tuples** per ticket
- 100,000 tickets, each updated 3 times on average = **300,000 dead tuples**

Dead tuples cause:
- **Bloated tables**: More pages to read, sequential scans get slower
- **Bloated indexes**: Index entries pointing to dead tuples waste space
- **Wasted disk**: Space that could be reused is occupied by ghosts

### 🛠️ Build: Create and Observe Bloat

<details>
<summary>💡 Hint 1: Direction</summary>
Query `pg_stat_user_tables` for `n_dead_tup` before and after running `UPDATE tickets SET updated_at = NOW() WHERE event_id BETWEEN 1 AND 10`. The dead tuple count should jump by the number of rows updated.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Calculate the dead tuple percentage: `round(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 1)`. Also check `pg_total_relation_size('tickets')` -- the table grows even though the live data has not changed, because dead tuples still occupy pages.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
After creating bloat, run `VACUUM tickets` and query `n_dead_tup` again -- it should drop to near zero. But check `pg_total_relation_size` -- it has NOT shrunk. VACUUM marks space as reusable but does not return it to the OS. Only `VACUUM FULL` (which locks the table) actually shrinks the file.
</details>


```sql
-- Step 1: Check current state
SELECT relname, n_live_tup, n_dead_tup,
       round(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 1) AS dead_pct,
       pg_size_pretty(pg_total_relation_size('tickets')) AS total_size
FROM pg_stat_user_tables
WHERE relname = 'tickets';

-- Step 2: Create 100K dead tuples by mass-updating
UPDATE tickets SET updated_at = NOW() WHERE event_id BETWEEN 1 AND 10;

-- Step 3: Check again
SELECT relname, n_live_tup, n_dead_tup,
       round(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 1) AS dead_pct,
       pg_size_pretty(pg_total_relation_size('tickets')) AS total_size
FROM pg_stat_user_tables
WHERE relname = 'tickets';
-- n_dead_tup should have jumped significantly!

-- Step 4: Now delete a bunch of rows and re-insert them
DELETE FROM tickets WHERE event_id = 20;
INSERT INTO tickets (event_id, section, row_num, seat, price, status, created_at, updated_at)
SELECT 20, 'Test', 'R1', 'S' || s, 50.00, 'available', NOW(), NOW()
FROM generate_series(1, 5000) AS s;

-- Step 5: Check dead tuples again
SELECT relname, n_live_tup, n_dead_tup,
       round(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 1) AS dead_pct
FROM pg_stat_user_tables
WHERE relname = 'tickets';
```


<details>
<summary>💡 Hint 1: Direction</summary>
Check `pg_stat_user_tables` for `n_dead_tup` before and after a mass UPDATE. The dead tuple count should jump significantly.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Run `UPDATE tickets SET updated_at = NOW() WHERE event_id BETWEEN 1 AND 10` to create dead tuples. Then query `n_live_tup` and `n_dead_tup` from `pg_stat_user_tables` to see the ratio.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Calculate `dead_pct` as `round(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 1)`. Also check `pg_total_relation_size('tickets')` — the table size grows with dead tuples even though the live data has not changed.
</details>

### 🛠️ Build: Run VACUUM and See the Difference

<details>
<summary>💡 Hint 1: Direction</summary>
Note the `n_dead_tup` count before running `VACUUM tickets`. After it completes, query `pg_stat_user_tables` again -- the count should drop to near zero. Compare `last_vacuum` timestamp to confirm it ran.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
VACUUM marks dead tuple space as reusable in the Free Space Map but does NOT shrink the file on disk. To reclaim disk space, you would need `VACUUM FULL` -- but it takes an ACCESS EXCLUSIVE lock that blocks all reads and writes. In production, prefer regular VACUUM.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
For TicketPulse's tickets table, tune autovacuum per-table: `ALTER TABLE tickets SET (autovacuum_vacuum_scale_factor = 0.01, autovacuum_vacuum_cost_delay = 0)`. This triggers vacuum at 1% dead tuples instead of the default 20%, and runs without throttling. Use `pg_stat_activity` to find long-running transactions that block vacuum.
</details>


```sql
-- Before vacuum: note n_dead_tup
SELECT n_dead_tup FROM pg_stat_user_tables WHERE relname = 'tickets';

-- Run vacuum
VACUUM tickets;

-- After vacuum
SELECT n_dead_tup FROM pg_stat_user_tables WHERE relname = 'tickets';
-- Should drop dramatically (possibly to 0)
```

What VACUUM does:
1. Scans the table for dead tuples (where `xmax` is committed and no active transaction can see them)
2. Marks the space as available in the **Free Space Map** (FSM)
3. Updates the **Visibility Map** (VM)
4. Updates statistics

What VACUUM does **NOT** do:
- Return disk space to the operating system (the file size stays the same)
- Lock the table (reads and writes continue during VACUUM)
- Reorder or defragment pages


<details>
<summary>💡 Hint 1: Direction</summary>
Note the `n_dead_tup` count before running VACUUM. After `VACUUM tickets`, check again — it should drop to near zero.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
VACUUM marks dead tuple space as reusable in the Free Space Map but does NOT shrink the file on disk. To actually reclaim disk space, you would need `VACUUM FULL` (which locks the table).
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
For TicketPulse's tickets table, tune autovacuum per-table: `ALTER TABLE tickets SET (autovacuum_vacuum_scale_factor = 0.01, autovacuum_vacuum_cost_delay = 0)`. This triggers vacuum at 1% dead tuples instead of the default 20%.
</details>

### 📊 Observe: Autovacuum in Action

Postgres runs vacuum automatically via the **autovacuum daemon**. Check when it last ran:

```sql
SELECT schemaname, relname,
       n_live_tup, n_dead_tup,
       last_vacuum, last_autovacuum,
       last_analyze, last_autoanalyze
FROM pg_stat_user_tables
WHERE relname = 'tickets';
```

Autovacuum triggers when:
```
dead_tuples > autovacuum_vacuum_threshold + (autovacuum_vacuum_scale_factor * table_rows)
Default: dead_tuples > 50 + (0.2 * table_rows)
```

For a 100K-row table, that means autovacuum triggers after **20,050 dead tuples** — that's a lot of bloat before cleanup starts!

### The High-Churn Table Problem

TicketPulse's tickets table updates constantly. The default autovacuum settings are too conservative.

```sql
-- Check current autovacuum settings for tickets
SELECT reloptions FROM pg_class WHERE relname = 'tickets';

-- Tune autovacuum for the tickets table specifically
ALTER TABLE tickets SET (
    autovacuum_vacuum_scale_factor = 0.01,    -- Trigger at 1% dead tuples (not 20%!)
    autovacuum_vacuum_threshold = 1000,        -- Base threshold
    autovacuum_vacuum_cost_delay = 0,          -- No throttling — vacuum as fast as possible
    autovacuum_analyze_scale_factor = 0.005    -- Update statistics more often
);

-- Verify
SELECT reloptions FROM pg_class WHERE relname = 'tickets';
```

### ⚠️ Common Mistake: Long-Running Transactions Block Vacuum

A dead tuple can't be vacuumed if any active transaction might still need to see it. One idle transaction from 3 hours ago prevents vacuum from cleaning up **all** tuples deleted in the last 3 hours.

```sql
-- Find long-running transactions blocking vacuum
SELECT pid, now() - xact_start AS duration, state, query
FROM pg_stat_activity
WHERE state != 'idle'
  AND xact_start < now() - interval '5 minutes'
ORDER BY xact_start;
```

Prevention:
```sql
-- Kill idle-in-transaction sessions after 5 minutes
ALTER SYSTEM SET idle_in_transaction_session_timeout = '5min';
SELECT pg_reload_conf();
```

---

## Part 4: Transaction ID Wraparound (10 min)

### The Silent Killer

PostgreSQL transaction IDs are 32-bit unsigned integers — max ~4.2 billion. Postgres uses modular arithmetic to compare transaction ages, and it can only look 2 billion transactions into the past.

If a tuple's `xmin` is more than 2 billion transactions old and hasn't been **frozen**, the database cannot determine its visibility. To prevent this catastrophe, vacuum **freezes** old tuples — replacing their `xmin` with a special `FrozenTransactionId`.

If autovacuum falls behind and the database approaches the wraparound limit, Postgres issues increasingly dire warnings and eventually **shuts down and refuses all write transactions**.

### 🔍 Try It: Check Your Wraparound Status

```sql
-- How close are you to wraparound danger?
SELECT datname, age(datfrozenxid) AS xid_age,
       current_setting('autovacuum_freeze_max_age')::bigint AS freeze_max,
       round(age(datfrozenxid)::numeric /
             current_setting('autovacuum_freeze_max_age')::bigint * 100, 1) AS pct_to_freeze
FROM pg_database
ORDER BY xid_age DESC;

-- Tables closest to wraparound
SELECT schemaname, relname, age(relfrozenxid) AS xid_age
FROM pg_stat_user_tables
ORDER BY xid_age DESC
LIMIT 10;
```

In a local development environment, these numbers will be small. In production with millions of transactions per day, this is something you monitor in your alerting dashboards.

### Why This Matters for TicketPulse

At scale, TicketPulse might process millions of ticket transactions per day during a big event launch (think Taylor Swift tickets). Each transaction burns a transaction ID. If autovacuum can't keep up with freezing old tuples, you're on a countdown to disaster.

---

## Part 5: Buffer Pool (10 min)

### Shared Buffers: PostgreSQL's Memory Cache

Every read and write in Postgres goes through the **shared buffer pool** — an in-memory cache of 8 KB pages.

```
Query needs page (0, 42)
    │
    ▼
Check shared_buffers → Found? (buffer hit) → Use it, no disk I/O
    │
    └── Not found? (buffer miss) → Read from disk → Load into shared_buffers → Use it
```

### 🔍 Try It: Measure Your Cache Hit Ratio

```sql
-- Overall buffer cache hit ratio
SELECT
    sum(heap_blks_read) AS heap_read,
    sum(heap_blks_hit) AS heap_hit,
    round(sum(heap_blks_hit)::numeric /
          NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0) * 100, 2) AS hit_ratio
FROM pg_statio_user_tables;
-- Target: > 99% for OLTP workloads
```

### The Double-Buffering Problem

Both Postgres and the OS cache data pages. A page might exist in shared_buffers AND the OS page cache, wasting memory. This is the **double buffering** problem.

The pragmatic solution:
- `shared_buffers` = **25-40% of total RAM** (not more)
- Let the OS use the remaining RAM for its page cache
- `effective_cache_size` = **50-75% of total RAM** (tells the planner how much total cache is available — doesn't allocate memory)

### Configuration for TicketPulse

For a typical production server with 16 GB RAM:

```
shared_buffers = 4GB               # 25% of RAM
effective_cache_size = 12GB         # 75% of RAM
work_mem = 64MB                     # Per sort/hash operation
maintenance_work_mem = 1GB          # For VACUUM, CREATE INDEX
```

**Warning about work_mem**: This is allocated **per sort/hash operation, per query, per connection**. With 100 connections each running a query with 3 sorts: 100 * 3 * 64MB = 19.2 GB. Be conservative globally, raise per-session for analytical queries:

```sql
SET work_mem = '256MB';
-- Run your analytical query
RESET work_mem;
```

### 📊 Observe: What's in Your Buffer Cache?

```sql
-- Requires pg_buffercache extension
CREATE EXTENSION IF NOT EXISTS pg_buffercache;

SELECT c.relname, count(*) AS buffers,
       pg_size_pretty(count(*) * 8192) AS buffered_size
FROM pg_buffercache b
JOIN pg_class c ON c.relfilenode = b.relfilenode
WHERE c.relname NOT LIKE 'pg_%'
GROUP BY c.relname
ORDER BY buffers DESC
LIMIT 10;
```

---

## 🤔 Reflect: Tuning TicketPulse's Tickets Table

TicketPulse's tickets table has high churn — tickets are created, reserved, sold, and expired constantly. Given what you now know about MVCC, WAL, and vacuum:

1. **Vacuum settings**: What `autovacuum_vacuum_scale_factor` would you set? Why?
2. **WAL implications**: During a major event launch (50K tickets sold in 10 minutes), how much WAL would you expect to generate? What settings would you tune?
3. **Buffer pool**: The tickets table is 100K rows today. If it grows to 10M rows, would all of it fit in shared_buffers? What happens when it doesn't?
4. **Dead tuple prevention**: Is there a way to reduce the number of dead tuples generated? (Hint: think about HOT updates — Heap-Only Tuple updates that avoid creating new index entries when the indexed columns don't change.)

<details>
<summary>Discussion</summary>

1. **Vacuum**: `autovacuum_vacuum_scale_factor = 0.01` (trigger at 1% dead tuples) with `autovacuum_vacuum_cost_delay = 0` (no throttling). The tickets table is small enough that aggressive vacuum won't impact performance.

2. **WAL**: 50K tickets * ~5 updates each * ~200 bytes per WAL record = ~50 MB of WAL in 10 minutes. That's modest. But if each ticket also updates associated order records and triggers index updates, it could be 10x more. Ensure `max_wal_size` is large enough (2-4 GB) to avoid checkpoint storms during the launch.

3. **Buffer pool**: 10M rows * ~200 bytes per row = ~2 GB of heap data. With a 4 GB shared_buffers, the hot working set should fit. But during a launch, the active tickets (available, recently reserved) are the hot set — maybe 500K rows. The rest are cold (sold, expired). Postgres's clock-sweep eviction handles this well.

4. **HOT updates**: If you UPDATE a ticket's status but don't change any indexed column, Postgres can do a HOT update — the new tuple stays on the same page and no index entries need updating. To enable this, ensure the page has free space (`fillfactor = 70` on the table) and avoid indexing the `status` column if possible. However, TicketPulse likely needs an index on status for "find available tickets" queries, which limits HOT update opportunities.

</details>

---

> **What did you notice?** Every UPDATE creates a dead tuple. For TicketPulse's high-churn tickets table, what does that mean for disk usage and query performance over time? How does autovacuum keep up?

## 🏁 Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **MVCC** | Readers never block writers. Every UPDATE creates a new tuple version. |
| **xmin/xmax** | Hidden columns that track which transaction created/deleted each row. |
| **WAL** | Sequential log of all changes. Guarantees crash recovery. Write-then-flush. |
| **Checkpoint** | Background process that writes dirty pages to data files. |
| **Vacuum** | Reclaims dead tuple space. Autovacuum defaults are too conservative for high-churn tables. |
| **TX ID Wraparound** | 32-bit TX IDs wrap around. Vacuum must freeze old tuples or the database stops. |
| **Buffer Pool** | 25-40% of RAM. Clock-sweep eviction. Double-buffering with OS cache. |

**The operational mindset**: In production, you monitor `n_dead_tup`, buffer cache hit ratio, autovacuum frequency, and transaction ID age. When any of these go wrong, you now know exactly why and how to fix it.

## What's Next

In **L2-M38: Connection Pooling**, you'll discover why TicketPulse's microservices are exhausting Postgres connections — and how PgBouncer fixes it.

## Key Terms

| Term | Definition |
|------|-----------|
| **MVCC** | Multi-Version Concurrency Control; PostgreSQL's method of allowing concurrent reads and writes without locking. |
| **WAL** | Write-Ahead Log; a log where changes are recorded before being applied to data files, ensuring crash recovery. |
| **Vacuum** | A PostgreSQL maintenance process that reclaims storage occupied by dead tuples and updates statistics. |
| **Dead tuple** | A row version that is no longer visible to any transaction and is eligible for cleanup by vacuum. |
| **Transaction ID** | A unique, monotonically increasing identifier assigned to each transaction in PostgreSQL. |
| **Shared buffers** | The portion of PostgreSQL's memory used to cache frequently accessed data pages from disk. |

## 📚 Further Reading
- [PostgreSQL Internals Documentation](https://www.postgresql.org/docs/current/internals.html)
- Chapter 24 of the 100x Engineer Guide: Sections 1.1-1.6
- [Postgres MVCC Explained](https://www.postgresql.org/docs/current/mvcc-intro.html)
- [Understanding VACUUM](https://www.cybertec-postgresql.com/en/postgresql-vacuum-and-analyze-best-practice-tips/)
- [pganalyze Blog: Tuning Autovacuum](https://pganalyze.com/blog/visualizing-and-tuning-postgres-autovacuum)
