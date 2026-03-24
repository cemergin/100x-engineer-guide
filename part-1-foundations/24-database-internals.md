<!--
  CHAPTER: 24
  TITLE: Database Internals, Optimization & Management
  PART: I — Foundations
  PREREQS: Chapter 2
  KEY_TOPICS: PostgreSQL internals, MVCC, WAL, vacuum, query planner, buffer pool, index internals, DynamoDB internals, MySQL InnoDB, query optimization, connection management, backup/recovery, migrations, performance tuning
  DIFFICULTY: Advanced
  UPDATED: 2026-03-24
-->

# Chapter 24: Database Internals, Optimization & Management

> **Part I — Foundations** | Prerequisites: Chapter 2 | Difficulty: Advanced

How databases actually work under the hood — the knowledge that lets you go from "it's slow" to "I know exactly why and how to fix it."

### In This Chapter
- PostgreSQL Internals
- MySQL/InnoDB Internals
- DynamoDB Internals
- Query Optimization Masterclass
- Index Deep Dive
- Connection Management
- Backup, Recovery & High Availability
- Database Performance Tuning
- Database Management & Operations
- SQL Mastery
- Graph Databases

### Related Chapters
- Ch 2 (database paradigms and data modeling)
- Ch 13 (databases in cloud context)
- Ch 18 (slow query debugging)
- Ch 19 (AWS RDS/Aurora/DynamoDB)

---

## 1. PostgreSQL Internals

PostgreSQL is an open-source, ACID-compliant relational database that has become the default choice for serious production workloads. Understanding its internals transforms you from someone who writes SQL into someone who can diagnose and fix any performance problem.

### 1.1 Storage Architecture

#### Heap Files, Pages, and Tuples

PostgreSQL stores table data in **heap files** — unordered collections of rows. There is no inherent ordering of rows on disk (unlike MySQL's InnoDB, which stores rows in primary key order).

Every heap file is divided into **pages** (also called blocks), each exactly **8 KB** in size. This is the fundamental unit of I/O in Postgres — the database always reads and writes entire 8 KB pages, even if you only need one row.

```
┌─────────────────────────────────────────────────────────────┐
│                        Page (8 KB)                          │
├──────────┬──────────────────────────────────────────────────┤
│  Page    │  Line Pointers (array of offsets)                │
│  Header  │  → points to tuple 1 at offset 8100             │
│  (24 B)  │  → points to tuple 2 at offset 7900             │
│          │  → points to tuple 3 at offset 7680             │
├──────────┴──────────────────────────────────────────────────┤
│                     Free Space                              │
├─────────────────────────────────────────────────────────────┤
│  Tuple 3 (220 bytes)                                       │
│  Tuple 2 (200 bytes)                                       │
│  Tuple 1 (100 bytes)                                       │
└─────────────────────────────────────────────────────────────┘
```

Key details:
- **Page header** (24 bytes): LSN (last WAL position that modified this page), checksum, flags
- **Line pointers**: Fixed-size array growing downward from the header. Each pointer holds the offset and length of a tuple. This indirection lets Postgres move tuples within a page without updating external references.
- **Tuples**: The actual row data, packed from the bottom of the page upward. Each tuple has a header (~23 bytes) containing `xmin`, `xmax`, `cmin`, `cmax`, `ctid`, null bitmap, and info mask.

The `ctid` (current tuple ID) is the physical address of a row: `(page_number, item_number)`. For example, `(0, 3)` means page 0, line pointer 3. Indexes store these ctids to locate rows.

#### TOAST (The Oversized Attribute Storage Technique)

A single tuple cannot span multiple pages. Since pages are 8 KB, any row wider than roughly 2 KB triggers **TOAST** — Postgres's mechanism for handling large values.

TOAST strategies per column:
- **PLAIN**: No TOAST (used for fixed-width types like `integer`)
- **EXTENDED** (default for variable-length types): Compress first, then store out-of-line if still too large
- **EXTERNAL**: Store out-of-line without compression (good for pre-compressed data like JPEG)
- **MAIN**: Compress first, only store out-of-line as last resort

TOAST values are stored in a separate **TOAST table** (one per table that needs it), linked by a TOAST pointer in the main tuple. Each TOAST table is itself a heap with its own indexes.

```sql
-- Check TOAST storage strategy per column
SELECT attname, attstorage
FROM pg_attribute
WHERE attrelid = 'your_table'::regclass AND attnum > 0;
-- 'p' = PLAIN, 'e' = EXTERNAL, 'x' = EXTENDED, 'm' = MAIN
```

**Practical implication**: If you `SELECT *` on a table with large `text` or `jsonb` columns, Postgres must fetch the TOAST table data too. Selecting only the columns you need avoids this overhead.

#### Tablespaces and Data Directory Structure

```
$PGDATA/
├── base/                    # Database files (one subdirectory per database OID)
│   ├── 1/                   # template1
│   ├── 13356/               # your_database (OID)
│   │   ├── 16384            # A table's first segment (heap file)
│   │   ├── 16384.1          # Second 1 GB segment of same table
│   │   ├── 16384_fsm        # Free space map
│   │   └── 16384_vm         # Visibility map
│   └── ...
├── global/                  # Cluster-wide tables (pg_database, pg_authid)
├── pg_wal/                  # Write-Ahead Log segments (16 MB each)
├── pg_xact/                 # Transaction commit status (commit log / clog)
├── pg_stat_tmp/             # Temporary statistics files
├── pg_tblspc/               # Symbolic links to tablespace locations
├── postgresql.conf          # Main configuration
├── pg_hba.conf              # Host-based authentication
└── postmaster.pid           # Lock file with PID
```

Key files per table:
- **Main fork** (`16384`): The heap data. Splits into 1 GB segments.
- **FSM (Free Space Map)** (`16384_fsm`): Tracks free space in each page so inserts can find pages with room.
- **VM (Visibility Map)** (`16384_vm`): Two bits per page — one indicating "all tuples visible to all transactions" (enables index-only scans), one indicating "all tuples frozen" (no need to vacuum).

```sql
-- Map relation name to file path
SELECT pg_relation_filepath('your_table');
-- Returns: base/13356/16384
```

---

### 1.2 MVCC (Multi-Version Concurrency Control)

MVCC is the mechanism that lets multiple transactions read and write data concurrently without blocking each other. Instead of locking rows for reads, Postgres keeps multiple versions of each row and lets each transaction see the version that was current when the transaction started.

#### How Postgres Implements MVCC

Every tuple in Postgres carries four hidden system columns:

| Column | Meaning |
|--------|---------|
| `xmin` | The transaction ID that **inserted** this tuple |
| `xmax` | The transaction ID that **deleted or updated** this tuple (0 if still live) |
| `cmin` | The command counter within the inserting transaction |
| `cmax` | The command counter within the deleting transaction |

```sql
-- You can actually see these hidden columns
SELECT xmin, xmax, ctid, * FROM your_table LIMIT 5;
```

When you **UPDATE** a row, Postgres does not modify the existing tuple in place. Instead it:
1. Sets `xmax` on the old tuple to the current transaction ID (marks it as "deleted by this transaction")
2. Inserts a brand new tuple with `xmin` = current transaction ID and `xmax` = 0
3. The old tuple's `t_ctid` pointer is updated to point to the new tuple (forming a version chain)

This is why UPDATE in Postgres is essentially DELETE + INSERT, and why it is more expensive than you might expect.

#### The Visibility Check

When a transaction reads a tuple, Postgres runs a visibility check. The simplified logic:

```
A tuple is VISIBLE to transaction T if:
  1. xmin is committed AND xmin was committed before T's snapshot
  2. AND (xmax is 0                           -- tuple is live
         OR xmax is aborted                   -- deleter rolled back
         OR xmax is not yet visible to T)     -- deleter hasn't committed yet from T's perspective
```

The actual check is more complex (handling in-progress transactions, sub-transactions, etc.), but this captures the core idea. This check runs for **every tuple** your query touches — it is cheap but not free.

#### Snapshot Isolation

When a transaction begins (or, under READ COMMITTED, when each statement begins), Postgres takes a **snapshot** — a record of:
- The current transaction ID
- A list of all transaction IDs that are currently in-progress (the "active transaction list")
- The lowest and highest active transaction IDs

A tuple's `xmin`/`xmax` is "visible" if the transaction that wrote it:
1. Is committed
2. Is not in the snapshot's active list
3. Has a transaction ID less than the snapshot's upper bound

This is how different transactions can see different versions of the same row at the same time — each has a different snapshot.

#### Read Phenomena

| Phenomenon | Description | Allowed in READ COMMITTED? | Allowed in REPEATABLE READ? | Allowed in SERIALIZABLE? |
|------------|-------------|------|------|------|
| Dirty read | See uncommitted data | No | No | No |
| Non-repeatable read | Same query returns different rows after another TX commits | Yes | No | No |
| Phantom read | New rows appear matching a previous query's WHERE | Yes | No | No |
| Write skew | Two TXs read overlapping data, make disjoint writes, creating an inconsistency | Yes | Yes | No |

PostgreSQL never allows dirty reads, even at READ COMMITTED. This is stricter than the SQL standard requires.

#### Isolation Levels in Practice

**READ COMMITTED** (default):
- Takes a new snapshot at the start of each **statement**
- If another transaction commits while yours is running, your next statement sees the new data
- Most applications use this and it works fine
- Can cause "lost updates" if two transactions read-then-write the same row

**REPEATABLE READ**:
- Takes one snapshot at the start of the **transaction**
- All statements in the transaction see the same data, regardless of other commits
- If you try to update a row that another committed transaction already modified, you get a serialization error: `could not serialize access due to concurrent update`
- You must retry the transaction on this error

**SERIALIZABLE**:
- Same as REPEATABLE READ, but also detects **write skew** anomalies
- Uses **Serializable Snapshot Isolation (SSI)** — tracks read dependencies between transactions
- If two transactions would create an anomaly, one is aborted with a serialization error
- More serialization failures = more retries, but guarantees the result is equivalent to some serial execution order

```sql
-- Example: Write skew (only caught by SERIALIZABLE)
-- Rule: At least one doctor must be on call

-- Transaction A:                           -- Transaction B:
BEGIN ISOLATION LEVEL SERIALIZABLE;         BEGIN ISOLATION LEVEL SERIALIZABLE;
SELECT count(*) FROM doctors                SELECT count(*) FROM doctors
  WHERE on_call = true;  -- returns 2        WHERE on_call = true;  -- returns 2
UPDATE doctors SET on_call = false           UPDATE doctors SET on_call = false
  WHERE id = 1;                               WHERE id = 2;
COMMIT;  -- succeeds                        COMMIT;  -- ERROR: serialization failure
                                            -- (one will be aborted)
```

---

### 1.3 WAL (Write-Ahead Log)

The Write-Ahead Log is how Postgres guarantees **durability** — the D in ACID. The rule is simple: before any change is written to the actual data file, a record of that change must first be written to the WAL and flushed to disk.

#### Why WAL Exists

Without WAL, a crash during a write could leave data files in an inconsistent state — a page half-written, an index pointing to a deleted row, etc. With WAL:
1. Changes are written sequentially to the WAL (sequential writes are fast)
2. Data files are updated later (in the background, at checkpoint time)
3. If the system crashes, Postgres replays the WAL from the last checkpoint to recover

This converts random writes (updating arbitrary pages in heap files) into sequential writes (appending to the WAL), which is dramatically faster on both spinning disks and SSDs.

#### WAL Write Path

```
SQL Statement
    │
    ▼
Modify page in shared buffers (in memory)
    │
    ▼
Write WAL record to WAL buffer (in memory)
    │
    ▼
On COMMIT: flush WAL buffer → WAL file on disk (fsync)
    │
    ▼
Return success to client
    │
    ... (later, at checkpoint time) ...
    │
    ▼
Background writer / checkpointer writes dirty pages from shared buffers → data files
```

Key points:
- The WAL buffer is in shared memory (size controlled by `wal_buffers`, default 1/32 of `shared_buffers`)
- WAL is flushed to disk on every `COMMIT` (controlled by `synchronous_commit`)
- Setting `synchronous_commit = off` lets the server return success before WAL is flushed — faster, but you can lose the last ~600ms of transactions on crash
- WAL files are 16 MB segments, named with monotonically increasing LSN-based names

#### Checkpoint Process

A **checkpoint** is when Postgres writes all dirty (modified) pages from shared buffers to their actual data files on disk. After a checkpoint, those WAL records are no longer needed for crash recovery.

```
postgresql.conf:
  checkpoint_timeout = 5min      # Max time between checkpoints
  max_wal_size = 1GB             # Triggers checkpoint when WAL grows this large
  checkpoint_completion_target = 0.9  # Spread checkpoint I/O over 90% of the interval
```

**Checkpoint storms**: If `max_wal_size` is too small or your write rate is very high, checkpoints happen too frequently and the checkpointer must flush many dirty pages at once, causing I/O spikes. Increase `max_wal_size` and `checkpoint_timeout` to spread the work.

#### WAL Archiving and Point-in-Time Recovery (PITR)

```
postgresql.conf:
  wal_level = replica              # Include enough info for replication/archiving
  archive_mode = on
  archive_command = 'cp %p /archive/%f'   # Copy each WAL segment to archive location
```

With a **base backup** (a full copy of the data directory) plus all WAL segments since that backup, you can recover to any point in time:

```bash
# Take a base backup
pg_basebackup -D /backup/base -Ft -Xs -P

# To recover to a specific time:
# 1. Restore the base backup
# 2. Copy archived WAL segments to pg_wal/
# 3. Set recovery target in postgresql.conf:
#    recovery_target_time = '2026-03-23 14:30:00'
#    restore_command = 'cp /archive/%f %p'
# 4. Create recovery.signal file and start Postgres
```

#### Streaming Replication

Instead of shipping WAL files, a standby connects directly to the primary and receives WAL records in real-time:

```
# Primary: postgresql.conf
wal_level = replica
max_wal_senders = 5

# Standby: primary_conninfo in postgresql.conf (or recovery.conf in older versions)
primary_conninfo = 'host=primary_ip port=5432 user=replicator'
```

Streaming replication is the foundation of PostgreSQL high availability. The standby can serve read-only queries (`hot_standby = on`), reducing load on the primary.

---

### 1.4 Vacuum

Vacuum is the most misunderstood part of Postgres, and misconfigured vacuum is the #1 cause of Postgres performance degradation in production.

#### Why Vacuum Is Necessary

Because of MVCC, every UPDATE creates a new tuple version and marks the old one as dead (by setting `xmax`). Every DELETE marks a tuple as dead. These **dead tuples** still occupy space on disk. They make sequential scans slower (more pages to read) and waste disk space.

VACUUM reclaims this space so it can be reused for future inserts.

#### Regular VACUUM

```sql
VACUUM your_table;
```

What it does:
1. Scans the table for dead tuples (those where `xmax` is committed and no active transaction can see them)
2. Marks the space occupied by dead tuples as available in the **Free Space Map**
3. Updates the **Visibility Map** (marking all-visible pages)
4. Updates `pg_stat_user_tables` statistics
5. Optionally freezes old transaction IDs (more on this below)

What it does NOT do:
- It does NOT return disk space to the operating system
- It does NOT lock the table (reads and writes continue)
- It does NOT reorder rows or defragment pages

After VACUUM, a table with 1M rows and 500K dead tuples still occupies the same amount of disk space — but the dead space is reusable for new inserts.

#### VACUUM FULL

```sql
VACUUM FULL your_table;   -- WARNING: acquires ACCESS EXCLUSIVE lock
```

This rewrites the entire table to a new file, compacting it and returning disk space to the OS. But it acquires an **ACCESS EXCLUSIVE lock** — no reads, no writes, nothing — for the entire duration. On a large table, this can take hours.

**In production, almost never use VACUUM FULL.** Instead, use `pg_repack` extension, which does the same thing without a long-held lock.

```sql
-- pg_repack: online table rewrite (no long lock)
-- Install the extension first, then:
pg_repack -d your_database -t your_table
```

#### Autovacuum

Postgres runs vacuum automatically via the **autovacuum daemon**. Key settings:

```
# Autovacuum triggers when:
#   dead_tuples > autovacuum_vacuum_threshold + (autovacuum_vacuum_scale_factor * table_rows)
# Default: dead_tuples > 50 + (0.2 * table_rows)
# For a 1M row table: triggers after 200,050 dead tuples — that's a LOT of bloat!

autovacuum_vacuum_threshold = 50         # Base threshold
autovacuum_vacuum_scale_factor = 0.2     # Fraction of table size
autovacuum_vacuum_cost_delay = 2ms       # Pause between I/O bursts (throttling)
autovacuum_vacuum_cost_limit = 200       # I/O budget per burst
```

For high-write tables, the defaults are too conservative. Tune per-table:

```sql
-- Aggressive autovacuum for a high-write table
ALTER TABLE events SET (
    autovacuum_vacuum_scale_factor = 0.01,    -- Trigger at 1% dead tuples
    autovacuum_vacuum_threshold = 1000,
    autovacuum_vacuum_cost_delay = 0,         -- No throttling
    autovacuum_analyze_scale_factor = 0.005   -- Update statistics more often too
);
```

#### Transaction ID Wraparound

PostgreSQL transaction IDs are 32-bit unsigned integers (max ~4.2 billion). To compare transaction ages, Postgres uses modular arithmetic — it can only look 2 billion transactions into the past. If a tuple's `xmin` is more than 2 billion transactions old and hasn't been **frozen** (marked as "definitely visible to everyone"), the database cannot determine its visibility.

To prevent this, vacuum **freezes** old tuples — replacing their `xmin` with a special `FrozenTransactionId`. This must happen before the wraparound horizon.

If autovacuum falls behind and the database approaches the wraparound limit, Postgres issues increasingly dire warnings and eventually **shuts down and refuses to process any more write transactions** until a manual vacuum is run.

```sql
-- Check how close you are to wraparound danger
SELECT datname, age(datfrozenxid) AS xid_age,
       current_setting('autovacuum_freeze_max_age')::bigint AS freeze_max
FROM pg_database
ORDER BY xid_age DESC;

-- If xid_age approaches 2 billion, you have a critical problem
-- Tables closest to wraparound:
SELECT schemaname, relname, age(relfrozenxid) AS xid_age
FROM pg_stat_user_tables
ORDER BY xid_age DESC
LIMIT 20;
```

#### Monitoring Vacuum

```sql
-- Dead tuples and last vacuum time per table
SELECT schemaname, relname,
       n_live_tup, n_dead_tup,
       round(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 1) AS dead_pct,
       last_vacuum, last_autovacuum,
       last_analyze, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 20;

-- Currently running vacuums
SELECT pid, datname, relid::regclass, phase,
       heap_blks_total, heap_blks_scanned, heap_blks_vacuumed
FROM pg_stat_progress_vacuum;
```

#### Common Vacuum Problems

**Problem: Autovacuum can't keep up with writes**
Symptoms: `n_dead_tup` keeps growing, table bloat increases, sequential scans get slower.
Fix: Lower `autovacuum_vacuum_scale_factor`, increase `autovacuum_vacuum_cost_limit`, decrease `autovacuum_vacuum_cost_delay` for that table. Increase `autovacuum_max_workers` if multiple tables are backed up.

**Problem: Long-running transactions prevent cleanup**
A dead tuple can't be vacuumed if any active transaction might still need to see it. One idle transaction from 3 hours ago prevents vacuum from cleaning up all tuples deleted in the last 3 hours.

```sql
-- Find long-running transactions blocking vacuum
SELECT pid, now() - xact_start AS duration, state, query
FROM pg_stat_activity
WHERE state != 'idle'
  AND xact_start < now() - interval '5 minutes'
ORDER BY xact_start;

-- The oldest active transaction's xmin
SELECT backend_xmin FROM pg_stat_activity WHERE backend_xmin IS NOT NULL ORDER BY backend_xmin LIMIT 1;
```

Fix: Set `idle_in_transaction_session_timeout` to automatically kill idle-in-transaction sessions. Ensure your application properly commits or rolls back transactions.

**Problem: Prepared transactions preventing vacuum**
A `PREPARE TRANSACTION` that is never committed or rolled back holds its snapshot forever.

```sql
-- Check for abandoned prepared transactions
SELECT * FROM pg_prepared_xacts;
-- Clean up: COMMIT PREPARED 'name' or ROLLBACK PREPARED 'name'
```

---

### 1.5 Query Planner

The query planner (also called the optimizer) is the component that takes your SQL query and decides *how* to execute it. A good plan takes milliseconds; a bad plan takes hours. Understanding the planner is the single most impactful skill for database performance.

#### Statistics: The Foundation

The planner relies on **statistics** about your data to estimate how many rows each operation will produce. These statistics are stored in `pg_statistic` (and the human-readable view `pg_stats`).

```sql
-- View statistics for a column
SELECT tablename, attname, null_frac, n_distinct, most_common_vals, most_common_freqs,
       correlation
FROM pg_stats
WHERE tablename = 'orders' AND attname = 'status';
```

Key statistics:
- **null_frac**: Fraction of rows that are NULL
- **n_distinct**: Number of distinct values (negative means fraction of total rows)
- **most_common_vals / most_common_freqs**: The most common values and their frequencies
- **histogram_bounds**: Boundaries of equal-population histogram buckets (for range queries)
- **correlation**: Physical ordering correlation (-1 to 1, how well the column's logical order matches its physical order on disk)

`ANALYZE` collects these statistics by sampling rows (default sample size: `default_statistics_target = 100`, meaning 300 * 100 = 30,000 rows are sampled).

```sql
-- Update statistics for a table
ANALYZE your_table;

-- Increase statistics target for a column that has unusual distribution
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 1000;
ANALYZE orders;
```

**Stale statistics are the #1 cause of bad query plans.** If you load a million rows and forget to ANALYZE, the planner still thinks the table has 10 rows and will choose a sequential scan even when an index scan would be faster.

#### Cost Model

The planner assigns a **cost** to every possible execution plan and picks the cheapest one. Costs are measured in arbitrary units, where one sequential page read = 1.0 by default.

```
seq_page_cost = 1.0        # Cost of reading one page sequentially
random_page_cost = 4.0     # Cost of reading one random page (default for HDD)
cpu_tuple_cost = 0.01      # Cost of processing one tuple
cpu_index_tuple_cost = 0.005  # Cost of processing one index entry
cpu_operator_cost = 0.0025 # Cost of one operator (comparison, etc.)
```

**Critical tuning for SSDs**: If you're on SSDs (which you almost certainly are), set `random_page_cost` to 1.1-1.5 instead of 4.0. The default value of 4.0 was chosen for spinning disks where random reads are 100x slower than sequential reads. On SSDs, random and sequential reads are nearly the same speed. With the default setting, the planner over-penalizes index scans and incorrectly chooses sequential scans.

```sql
-- Per-tablespace setting (recommended if you know the storage type)
ALTER TABLESPACE pg_default SET (random_page_cost = 1.1);

-- Or globally
ALTER SYSTEM SET random_page_cost = 1.1;
SELECT pg_reload_conf();
```

#### Plan Types

**Scan types** (how to read rows from a table):

| Plan Node | When Used | Description |
|-----------|-----------|-------------|
| **Seq Scan** | Few rows in table, or need most rows | Reads every page of the table sequentially |
| **Index Scan** | Selective lookup on indexed column | Reads the index to find matching ctids, then fetches each tuple from the heap (random I/O) |
| **Index Only Scan** | Query can be satisfied entirely from the index | Reads only the index; never touches the heap. Requires the visibility map to confirm tuple visibility. |
| **Bitmap Index Scan** | Medium selectivity | Reads the index, builds a bitmap of matching pages, then reads those pages in physical order (converts random I/O to sequential) |
| **TID Scan** | Query filters on ctid directly | Rare; direct physical access |

**Join types**:

| Plan Node | When Used | Description |
|-----------|-----------|-------------|
| **Nested Loop** | One side is very small, or has an index | For each row on the outer side, scan the inner side. O(N * M) without index, O(N * log M) with index. |
| **Hash Join** | Moderate-to-large tables, equijoin | Build a hash table from the smaller side, probe it with each row of the larger side. O(N + M). Needs memory (work_mem). |
| **Merge Join** | Both sides already sorted (or have indexes) | Walk through both sorted inputs simultaneously. O(N + M) but requires sorted input. |

**Other nodes**:
- **Sort**: In-memory quicksort if fits in `work_mem`, otherwise external merge sort on disk
- **Aggregate**: GroupAggregate (sorted input), HashAggregate (hash table of groups)
- **Materialize**: Cache the output of a subquery in memory
- **Gather / Gather Merge**: Parallel query coordination

#### EXPLAIN ANALYZE Deep Dive

`EXPLAIN` shows the plan. `EXPLAIN ANALYZE` actually **runs the query** and shows real timings.

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT u.name, count(o.id) as order_count
FROM users u
JOIN orders o ON o.user_id = u.id
WHERE u.status = 'active'
  AND o.created_at > '2025-01-01'
GROUP BY u.name
ORDER BY order_count DESC
LIMIT 10;
```

Example output (annotated):

```
Limit  (cost=1234.56..1234.59 rows=10 width=40) (actual time=45.2..45.3 rows=10 loops=1)
  ->  Sort  (cost=1234.56..1237.89 rows=1332 width=40) (actual time=45.2..45.2 rows=10 loops=1)
        Sort Key: (count(o.id)) DESC
        Sort Method: top-N heapsort  Memory: 26kB
        ->  HashAggregate  (cost=1200.00..1213.32 rows=1332 width=40) (actual time=44.8..44.9 rows=1332 loops=1)
              Group Key: u.name
              Batches: 1  Memory Usage: 240kB
              ->  Hash Join  (cost=120.00..1180.00 rows=4000 width=36) (actual time=2.1..38.5 rows=4312 loops=1)
                    Hash Cond: (o.user_id = u.id)
                    ->  Index Scan using idx_orders_created on orders o  (cost=0.43..950.00 rows=50000 width=12)
                          (actual time=0.02..25.3 rows=48231 loops=1)
                          Index Cond: (created_at > '2025-01-01'::date)
                          Buffers: shared hit=4521 read=312
                    ->  Hash  (cost=100.00..100.00 rows=1600 width=28) (actual time=1.8..1.8 rows=1587 loops=1)
                          Buckets: 2048  Batches: 1  Memory Usage: 112kB
                          ->  Seq Scan on users u  (cost=0.00..100.00 rows=1600 width=28)
                                (actual time=0.01..1.2 rows=1587 loops=1)
                                Filter: (status = 'active')
                                Rows Removed by Filter: 413
                                Buffers: shared hit=50
Planning Time: 0.4 ms
Execution Time: 45.5 ms
```

How to read this:

1. **cost=X..Y**: X = estimated startup cost (before first row emitted), Y = estimated total cost. Units are in `seq_page_cost` multiples.
2. **rows=Z**: Estimated number of rows. Compare with `actual rows` — big discrepancies indicate bad statistics.
3. **actual time=A..B**: A = time to first row (ms), B = time to last row (ms). These are cumulative for that node and include children.
4. **loops=N**: How many times this node executed (important for nested loops). Multiply `actual time` by `loops` to get real total time.
5. **Buffers**: `shared hit` = pages found in shared buffers (cache), `shared read` = pages read from disk (or OS cache). High `read` values indicate cache misses.
6. **Rows Removed by Filter**: Rows that were fetched but didn't match the WHERE clause — indicates the index wasn't selective enough or there is no index for that predicate.

**Red flags in EXPLAIN ANALYZE**:
- Estimated rows vs actual rows differ by 10x or more → run `ANALYZE`
- `Rows Removed by Filter` is high → missing or wrong index
- `Sort Method: external merge` → not enough `work_mem`, spilling to disk
- `Buffers: shared read` is very high → working set doesn't fit in shared buffers
- Nested Loop with high `loops` count and no inner index → O(N*M) situation
- `HashAggregate Batches: >1` → spilling hash table to disk

#### Common Planner Mistakes and Fixes

**Stale statistics**: After bulk loads, schema changes, or significant data changes:
```sql
ANALYZE your_table;
-- Or for the whole database:
ANALYZE;
```

**Bad cardinality estimates with correlated columns**: The planner assumes column values are independent. If `city = 'San Francisco'` AND `state = 'CA'` are correlated, the planner underestimates the combined selectivity.
```sql
-- Extended statistics for correlated columns (Postgres 10+)
CREATE STATISTICS stats_city_state (dependencies) ON city, state FROM addresses;
ANALYZE addresses;
```

**Planner choosing Seq Scan when Index Scan would be faster**: Check `random_page_cost` (lower it for SSDs), run `ANALYZE`, and verify the index exists. You can also check if the planner's cost estimate is wrong:
```sql
-- Temporarily disable seq scan to see the alternative plan
SET enable_seqscan = off;
EXPLAIN ANALYZE SELECT ...;
-- Compare the actual execution times, then reset
RESET enable_seqscan;
```

**pg_hint_plan extension** (when you need to force a plan):
Postgres doesn't have native optimizer hints. The `pg_hint_plan` extension adds them:
```sql
/*+ IndexScan(orders idx_orders_user) HashJoin(users orders) */
SELECT * FROM users JOIN orders ON orders.user_id = users.id WHERE ...;
```

---

### 1.6 Buffer Pool

The **shared buffer pool** is PostgreSQL's main memory cache for data pages. Every read and write goes through shared buffers.

#### How It Works

- Shared buffers hold copies of 8 KB pages from data files
- When a query needs a page, Postgres first checks shared buffers
- If found (**buffer hit**), no disk I/O needed
- If not found (**buffer miss**), the page is read from disk (or OS cache) into a free buffer slot
- Modified pages are marked **dirty** and eventually written to disk by the checkpointer or background writer

#### Clock Sweep Eviction

When shared buffers are full and a new page needs to be loaded, Postgres must evict an existing page. It uses a **clock sweep** algorithm (a variant of LRU):

- Each buffer has a usage counter (0-5)
- When a page is accessed, its counter is incremented (up to 5)
- The "clock hand" sweeps through buffers; each pass decrements the counter
- A buffer with counter 0 is evicted
- Frequently accessed pages accumulate higher counters and survive more sweeps

#### Double Buffering Problem

Both Postgres and the operating system cache data pages. A page might be in shared buffers AND in the OS page cache — wasting memory. This is the **double buffering** problem.

The pragmatic solution:
- Set `shared_buffers` to **25-40% of total RAM** (not more)
- Let the OS use the remaining RAM for its page cache
- Set `effective_cache_size` to **50-75% of total RAM** — this doesn't allocate memory, it just tells the planner how much total cache (shared buffers + OS cache) is available, influencing its cost estimates for index scans

```sql
-- Monitoring buffer cache hit ratio
SELECT
    sum(heap_blks_read) AS heap_read,
    sum(heap_blks_hit) AS heap_hit,
    round(sum(heap_blks_hit)::numeric /
          NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0) * 100, 2) AS hit_ratio
FROM pg_statio_user_tables;
-- Target: > 99% hit ratio for OLTP workloads

-- Which tables are using the most buffer cache?
-- (requires pg_buffercache extension)
CREATE EXTENSION IF NOT EXISTS pg_buffercache;
SELECT c.relname, count(*) AS buffers,
       pg_size_pretty(count(*) * 8192) AS buffered_size
FROM pg_buffercache b
JOIN pg_class c ON c.relfilenode = b.relfilenode
WHERE c.relname NOT LIKE 'pg_%'
GROUP BY c.relname
ORDER BY buffers DESC
LIMIT 20;
```

#### Configuration Guidelines

```
# For a server with 64 GB RAM:
shared_buffers = 16GB          # 25% of RAM
effective_cache_size = 48GB    # 75% of RAM (shared_buffers + OS cache)
work_mem = 64MB                # Per-sort/hash operation — careful!
maintenance_work_mem = 2GB     # For VACUUM, CREATE INDEX
huge_pages = try               # Use huge pages if available (reduces TLB misses)
```

**Warning about work_mem**: This is allocated **per sort/hash operation, per query, per connection**. If you have 100 connections each running a query with 3 sort operations, that is 100 * 3 * 64MB = 19.2 GB just for sorts. Set it conservatively globally and raise it per-session when needed:

```sql
-- Raise for a specific analytical query
SET work_mem = '256MB';
SELECT ... complex analytical query ...;
RESET work_mem;
```

---

## 2. MySQL / InnoDB Internals

MySQL's default storage engine, InnoDB, takes a fundamentally different approach from PostgreSQL in several areas.

### 2.1 InnoDB Architecture

```
┌─────────────────────────────────────────────────────┐
│                    InnoDB Architecture               │
├─────────────────────────────────────────────────────┤
│  Buffer Pool (pages cached in memory)               │
│  ├── Data pages (clustered index pages)             │
│  ├── Index pages (secondary index pages)            │
│  ├── Undo log pages                                 │
│  ├── Change buffer                                  │
│  └── Adaptive hash index                            │
├─────────────────────────────────────────────────────┤
│  Redo Log (WAL equivalent) — circular log files     │
│  Undo Log — for MVCC rollback and read views        │
│  Doublewrite Buffer — crash safety for torn pages   │
├─────────────────────────────────────────────────────┤
│  Tablespace files (.ibd) — data + indexes           │
└─────────────────────────────────────────────────────┘
```

#### Buffer Pool

The buffer pool is InnoDB's equivalent of Postgres shared buffers, but it caches everything — data pages, index pages, undo pages, and the change buffer. It uses a modified LRU list split into "young" (frequently accessed) and "old" (recently loaded) sublists. New pages enter the old sublist midpoint; only pages accessed again after a short delay are promoted to the young sublist. This prevents table scans from flushing out frequently used pages.

```sql
-- Buffer pool status
SHOW ENGINE INNODB STATUS\G

-- Key metrics
SELECT * FROM information_schema.INNODB_BUFFER_POOL_STATS;
```

#### Redo Log (Equivalent of WAL)

InnoDB uses a redo log for crash recovery, conceptually identical to Postgres WAL but implemented as circular log files. Changes are first written to the redo log, then data pages are flushed later.

```
# MySQL 8.0+
innodb_redo_log_capacity = 4G    # Total redo log space (replaces innodb_log_file_size)
```

#### Doublewrite Buffer

InnoDB pages are 16 KB, but most filesystems write in 4 KB blocks. A crash during a page write could result in a partially written (torn) page. The doublewrite buffer prevents this by writing pages to a sequential area first, then to their actual location. If a torn page is detected on recovery, the copy from the doublewrite buffer is used.

PostgreSQL avoids this problem with full-page writes in WAL (writing the complete before-image of a page the first time it's modified after a checkpoint).

### 2.2 Clustered Index

This is the most important architectural difference from PostgreSQL.

In InnoDB, the table data itself is stored in the **primary key index** (a B+tree). The leaf nodes of the primary key index contain the full row data. This is called a **clustered index**.

```
InnoDB (Clustered):                PostgreSQL (Heap):

Primary Key B+tree                 Heap File (unordered rows)
├── [1] → {id:1, name:"Alice"}    ├── Page 0: [tuple1, tuple2, ...]
├── [2] → {id:2, name:"Bob"}      ├── Page 1: [tuple3, tuple4, ...]
├── [3] → {id:3, name:"Carol"}    └── Page 2: [tuple5, ...]
└── ...
                                   Primary Key Index (separate B+tree)
                                   ├── [1] → (0, 1)  ← ctid
                                   ├── [2] → (0, 2)
                                   └── [3] → (1, 1)
```

Consequences:
- **Primary key lookups are very fast** in InnoDB — traverse the B+tree and the data is right there
- **Range scans on the primary key are efficient** — rows are physically adjacent
- **Inserts with random primary keys (UUIDs) cause page splits** and fragmentation — rows must be inserted in PK order. Sequential/auto-increment PKs are strongly preferred in InnoDB.
- **The table is the primary key index** — there is no separate heap file

### 2.3 Secondary Indexes: The Double Lookup

In InnoDB, secondary indexes store the **primary key value** (not a physical row pointer like Postgres's ctid). To look up a row by a secondary index:

1. Traverse the secondary index B+tree → find the primary key value
2. Traverse the primary key (clustered) index B+tree → find the actual row data

This is called a **double lookup** or **bookmark lookup**. It makes secondary index lookups more expensive than in Postgres (where the index stores a direct physical pointer to the heap tuple).

```
Secondary Index on (email):
├── ["alice@ex.com"] → PK=1
├── ["bob@ex.com"]   → PK=2
└── ["carol@ex.com"] → PK=3

To find row: email index → PK=2 → clustered index lookup → row data
```

Implications:
- **Wide primary keys make all secondary indexes larger** (every secondary index stores a copy of the PK)
- Using a UUID (16 bytes) as PK instead of a BIGINT (8 bytes) adds 8 bytes per entry in every secondary index
- **Covering indexes** are extra valuable in InnoDB — if the secondary index contains all needed columns (including the PK columns, which are always implicitly included), the double lookup is avoided

### 2.4 InnoDB Locking

InnoDB uses row-level locking with several lock types:

- **Record lock**: Lock on a single index record
- **Gap lock**: Lock on the gap between index records (prevents inserts in that range)
- **Next-key lock**: Record lock + gap lock on the gap before it (default for REPEATABLE READ, prevents phantom reads)

```sql
-- See current locks
SELECT * FROM performance_schema.data_locks;

-- See lock waits
SELECT * FROM performance_schema.data_lock_waits;
```

Gap locks are a frequent source of confusion and deadlocks. They only exist at REPEATABLE READ and higher isolation levels. At READ COMMITTED, InnoDB only uses record locks.

### 2.5 MVCC in InnoDB

InnoDB implements MVCC differently from Postgres:
- Old row versions are stored in the **undo log** (not as separate tuples in the main table)
- Reading an old version requires applying undo records to reconstruct the historical version
- The **purge thread** (equivalent of Postgres vacuum) periodically removes undo records that are no longer needed by any active transaction
- There is no need for a separate VACUUM process — the purge thread handles this automatically

Advantage: No table bloat from dead tuples (the main table stays compact).
Disadvantage: Long-running transactions force the undo log to grow, and reconstructing old versions from a long chain of undo records is expensive.

### 2.6 Key Differences from PostgreSQL

| Feature | PostgreSQL | InnoDB (MySQL) |
|---------|-----------|------|
| Row storage | Heap (unordered) | Clustered index (PK-ordered) |
| Index pointers | Physical (ctid) | Logical (primary key) |
| Dead tuple handling | VACUUM | Purge thread (undo log) |
| Table bloat | Yes (needs VACUUM) | Minimal (but undo log can bloat) |
| MVCC old versions | In-place (heap) | Undo log |
| Page size | 8 KB | 16 KB |
| Partial indexes | Yes | No |
| Expression indexes | Yes | Generated columns + index |
| TOAST | Automatic for large values | ROW_FORMAT=DYNAMIC/COMPRESSED |
| Full-text search | tsvector/tsquery (built-in) | InnoDB FTS |

---

## 3. DynamoDB Internals

DynamoDB is a fully managed NoSQL key-value and document database. Its internal architecture is fundamentally different from relational databases.

### 3.1 Partition Architecture

Every DynamoDB table is divided into **partitions**. Each partition:
- Stores a range of items based on the **hash of the partition key**
- Is backed by SSD storage
- Is replicated across 3 Availability Zones
- Can handle up to 3,000 RCU and 1,000 WCU (read/write capacity units)

```
Request → Request Router → Partition Map → Storage Node

Table: Orders (partition key: order_id)

Partition 1 (hash range 0x0000-0x5555):
  ├── order_id: "abc" → {item data}
  ├── order_id: "def" → {item data}
  └── ...

Partition 2 (hash range 0x5556-0xAAAA):
  ├── order_id: "ghi" → {item data}
  └── ...

Partition 3 (hash range 0xAAAB-0xFFFF):
  ├── order_id: "jkl" → {item data}
  └── ...
```

The **request router** is a stateless fleet that:
1. Authenticates the request
2. Looks up the **partition map** to find which storage node holds the target partition
3. Routes the request to the correct storage node

The partition map is managed by a metadata service and cached in the request routers for low-latency lookups.

### 3.2 Adaptive Capacity

DynamoDB automatically handles uneven workloads:

- **Partition splitting**: If a partition becomes a hot spot, DynamoDB can split it into sub-partitions (even within a single partition key's sort key range)
- **Burst capacity**: Each partition retains unused capacity for up to 5 minutes, allowing short traffic bursts of up to 300 seconds of unused throughput
- **Adaptive capacity**: If one partition is hot and another is cold, DynamoDB can reallocate capacity from cold to hot partitions in real-time (even exceeding the per-partition limit)

Despite adaptive capacity, extreme hot keys can still cause throttling. DynamoDB cannot split below a single partition key.

### 3.3 Hot Partition Problem

When a disproportionate number of requests target the same partition key, that partition becomes a bottleneck.

**Example**: Using `date` as the partition key for a time-series table. All writes go to today's date partition.

**Solutions**:

1. **Write sharding**: Append a random suffix to the partition key
```
Instead of: PK = "2026-03-24"
Use:        PK = "2026-03-24#3"  (suffix from 0-9, spreading across 10 partitions)
```
Reads now require querying all 10 shards and merging results.

2. **Composite keys**: Design the partition key to include a dimension that naturally distributes writes
```
PK = "TENANT#acme"   (if tenants have roughly equal write rates)
SK = "2026-03-24#order_id"
```

3. **Caching**: Put DynamoDB Accelerator (DAX) or ElastiCache in front of hot read keys.

### 3.4 DynamoDB Streams

DynamoDB Streams provides a time-ordered sequence of item-level changes (inserts, updates, deletes) in a table.

Internally:
- Each partition maintains its own shard in the stream
- When a partition splits, the corresponding stream shard also splits
- Stream records are available for 24 hours
- Each stream record contains the old and/or new item image (configurable: KEYS_ONLY, NEW_IMAGE, OLD_IMAGE, NEW_AND_OLD_IMAGES)

Streams are the foundation for:
- Lambda triggers (event-driven processing)
- Global tables replication
- Change data capture (CDC) pipelines

### 3.5 Consistency Models

- **Eventually consistent reads** (default): The request router can serve the read from any of the 3 replicas. A recently written item may not be visible immediately (usually consistent within ~100ms). Costs 0.5 RCU per 4 KB.
- **Strongly consistent reads**: The request router routes to the **leader** replica (the one that accepts writes). Guaranteed to reflect all writes that completed before the read. Costs 1.0 RCU per 4 KB. Only works within a single region.

Under the hood, DynamoDB uses a Paxos-like consensus protocol. Writes must be acknowledged by 2 of 3 replicas (quorum). The leader orchestrates this.

### 3.6 On-Demand vs Provisioned Capacity

**Provisioned**: You specify RCU/WCU. DynamoDB pre-allocates capacity across partitions. Auto-scaling (via Application Auto Scaling) can adjust based on CloudWatch metrics, but has a ~5 minute reaction delay.

**On-demand**: DynamoDB automatically allocates capacity based on traffic. Internally, it tracks recent traffic levels and provisions double the previous peak. If traffic suddenly spikes to 10x normal, there is a brief throttling period while DynamoDB scales up. On-demand costs ~6x more per request than provisioned at steady state.

**When to use which**:
- On-demand: unpredictable traffic, new tables where you don't know the pattern, infrequent but spiky workloads
- Provisioned + auto-scaling: predictable traffic, cost-sensitive, high-throughput steady-state

### 3.7 Global Tables

DynamoDB Global Tables provide multi-region, multi-active replication.

- Every region has a full read/write replica
- Changes are replicated asynchronously (typically under 1 second, but no SLA)
- Conflict resolution: **last-writer-wins** based on a per-item timestamp
- Uses DynamoDB Streams internally for replication
- Consistency caveat: strong consistency reads only see local region's data

---

## 4. Query Optimization Masterclass

### 4.1 Reading EXPLAIN ANALYZE

Let's walk through a realistic example step by step.

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT c.name, count(o.id) as total_orders, sum(o.amount) as total_spent
FROM customers c
JOIN orders o ON o.customer_id = c.id
WHERE c.region = 'US'
  AND o.created_at BETWEEN '2025-01-01' AND '2025-12-31'
GROUP BY c.name
HAVING sum(o.amount) > 1000
ORDER BY total_spent DESC;
```

```
Sort  (cost=2345.67..2348.12 rows=980 width=48)
      (actual time=156.3..156.4 rows=842 loops=1)
  Sort Key: (sum(o.amount)) DESC
  Sort Method: quicksort  Memory: 92kB
  Buffers: shared hit=12453 read=2341
  ->  HashAggregate  (cost=2300.00..2325.00 rows=980 width=48)
                     (actual time=154.1..155.2 rows=842 loops=1)
        Group Key: c.name
        Filter: (sum(o.amount) > '1000'::numeric)
        Rows Removed by Filter: 2156
        Batches: 1  Memory Usage: 553kB
        ->  Hash Join  (cost=125.00..2100.00 rows=15000 width=44)
                       (actual time=3.2..120.5 rows=14832 loops=1)
              Hash Cond: (o.customer_id = c.id)
              ->  Bitmap Heap Scan on orders o  (cost=45.00..1800.00 rows=52000 width=20)
                                                (actual time=1.5..95.3 rows=51234 loops=1)
                    Recheck Cond: (created_at >= '2025-01-01' AND created_at <= '2025-12-31')
                    Heap Blocks: exact=8234
                    Buffers: shared hit=8123 read=2341
                    ->  Bitmap Index Scan on idx_orders_created_at  (cost=0.00..32.00 rows=52000 width=0)
                                                                    (actual time=1.2..1.2 rows=51234 loops=1)
                          Index Cond: (created_at >= '2025-01-01' AND created_at <= '2025-12-31')
              ->  Hash  (cost=65.00..65.00 rows=1200 width=28)
                        (actual time=1.5..1.5 rows=1187 loops=1)
                    Buckets: 2048  Batches: 1  Memory Usage: 85kB
                    ->  Seq Scan on customers c  (cost=0.00..65.00 rows=1200 width=28)
                                                 (actual time=0.01..0.8 rows=1187 loops=1)
                          Filter: (region = 'US'::text)
                          Rows Removed by Filter: 813
                          Buffers: shared hit=40
Planning Time: 0.8 ms
Execution Time: 156.9 ms
```

**Reading this bottom-up** (execution order):

1. **Seq Scan on customers**: Scans all 2000 customers, filters to 1187 US customers. The "Rows Removed by Filter: 813" means 813 rows were read but discarded. With only 2000 total rows, a Seq Scan is correct — an index would cost more overhead than just reading 40 pages.

2. **Hash**: Builds a hash table from the 1187 US customers. Fits in 85 KB of memory. Fast.

3. **Bitmap Index Scan on idx_orders_created_at**: Uses the index to find all 51,234 orders from 2025. A Bitmap scan was chosen because 51K rows is too many for an Index Scan (too many random heap reads) but too few for a Seq Scan (would read the whole table).

4. **Bitmap Heap Scan on orders**: Reads the 8,234 heap pages identified by the bitmap in physical order. `shared hit=8123 read=2341` — most pages were in cache, but 2,341 required disk reads. This is where the query spends most of its time (95ms).

5. **Hash Join**: For each of the 51,234 orders, probes the hash table of US customers. Produces 14,832 matching rows. The reduction from 51K to 15K means many orders belong to non-US customers.

6. **HashAggregate**: Groups the 14,832 rows by customer name. The HAVING filter removes 2,156 groups (customers who spent $1,000 or less), leaving 842.

7. **Sort**: Sorts 842 rows by total_spent DESC. Fits in memory (quicksort, 92 KB).

**Where to optimize this query**:
- The biggest cost is the Bitmap Heap Scan reading 2,341 pages from disk. Consider a **composite index** `(created_at, customer_id, amount)` for a potential index-only scan
- If this query runs frequently, a **materialized view** refreshed periodically would eliminate the work entirely
- The Seq Scan on customers is fine — small table, no optimization needed

### 4.2 Common Query Anti-Patterns and Fixes

#### SELECT *

```sql
-- Bad: Fetches all columns, prevents index-only scans, reads TOAST data
SELECT * FROM orders WHERE customer_id = 42;

-- Good: Only what you need
SELECT id, amount, created_at FROM orders WHERE customer_id = 42;
```

Index-only scans require ALL selected columns to be in the index. `SELECT *` makes this nearly impossible.

#### Functions on Indexed Columns

```sql
-- Bad: Cannot use index on created_at
SELECT * FROM orders WHERE YEAR(created_at) = 2025;
SELECT * FROM orders WHERE EXTRACT(YEAR FROM created_at) = 2025;

-- Good: Rewrite as range condition (uses index)
SELECT * FROM orders
WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01';
```

```sql
-- Bad: Cannot use index on email
SELECT * FROM users WHERE LOWER(email) = 'alice@example.com';

-- Fix option 1: Expression index
CREATE INDEX idx_users_email_lower ON users (LOWER(email));

-- Fix option 2: Collation (if your use case allows)
-- Store emails already lowercased and use a citext column type
```

#### Implicit Type Casting

```sql
-- Bad: phone is varchar, but comparing with integer — index not used
SELECT * FROM users WHERE phone = 5551234567;

-- Good: Match the column type
SELECT * FROM users WHERE phone = '5551234567';
```

Postgres will cast the entire column to match the literal's type, preventing index use.

#### OR Conditions

```sql
-- Bad: Often results in Seq Scan (can't efficiently use separate indexes)
SELECT * FROM orders WHERE customer_id = 42 OR product_id = 99;

-- Good: Rewrite as UNION ALL (each branch can use its own index)
SELECT * FROM orders WHERE customer_id = 42
UNION ALL
SELECT * FROM orders WHERE product_id = 99 AND customer_id != 42;
```

Note: Postgres's Bitmap OR can sometimes handle OR conditions, but UNION ALL is more reliably optimizable.

#### NOT IN with NULLs

```sql
-- Dangerous: Returns no rows if any value in subquery is NULL
SELECT * FROM users WHERE id NOT IN (SELECT user_id FROM blacklist);
-- If blacklist contains a NULL user_id, the entire NOT IN returns FALSE

-- Safe: NOT EXISTS handles NULLs correctly
SELECT * FROM users u
WHERE NOT EXISTS (SELECT 1 FROM blacklist b WHERE b.user_id = u.id);
```

#### Correlated Subqueries

```sql
-- Slow: Executes the subquery once per row in users
SELECT *, (SELECT count(*) FROM orders o WHERE o.user_id = u.id) AS order_count
FROM users u;

-- Fast: Single join and aggregate
SELECT u.*, count(o.id) AS order_count
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
GROUP BY u.id;

-- Alternative: Lateral join (useful for top-N per group)
SELECT u.*, recent.*
FROM users u
CROSS JOIN LATERAL (
    SELECT id, amount, created_at
    FROM orders o
    WHERE o.user_id = u.id
    ORDER BY created_at DESC
    LIMIT 3
) recent;
```

#### OFFSET Pagination

```sql
-- Terrible for deep pages: OFFSET 1000000 reads and discards 1M rows
SELECT * FROM orders ORDER BY created_at DESC LIMIT 20 OFFSET 1000000;

-- Good: Keyset (cursor) pagination — constant performance regardless of page depth
-- First page:
SELECT * FROM orders ORDER BY created_at DESC, id DESC LIMIT 20;
-- Next page (use the last row's values as the cursor):
SELECT * FROM orders
WHERE (created_at, id) < ('2025-06-15 14:30:00', 99823)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

Keyset pagination requires a unique, orderable cursor (usually `created_at` + `id` to break ties).

#### COUNT(*) on Large Tables

```sql
-- Slow: Requires a full table scan in Postgres (MVCC means there's no single "row count")
SELECT count(*) FROM orders;  -- May take seconds on millions of rows

-- Approximate (instant): Use the statistics collector's estimate
SELECT reltuples::bigint AS estimate FROM pg_class WHERE relname = 'orders';

-- Exact but maintained: Use a counter table updated by triggers
-- (trade write overhead for instant read)
```

### 4.3 Index Optimization

#### When to Add an Index (and When NOT To)

Add an index when:
- A query frequently filters/sorts on a column and it's doing Seq Scans
- The column has high selectivity (many distinct values relative to total rows)
- The table is large enough that Seq Scan is actually slow

Do NOT add an index when:
- The table is small (< 10K rows) — Seq Scan is fine
- The column has very low selectivity (boolean, status with 3 values) — the planner will choose Seq Scan anyway because most rows match
- The table is write-heavy and the index isn't used by any query — each index adds overhead to every INSERT, UPDATE, DELETE
- You already have many indexes on the table — diminishing returns, increasing write overhead

#### Composite Index Column Ordering

The **leftmost prefix rule**: A composite index on `(a, b, c)` can be used for queries filtering on:
- `a` alone
- `a` AND `b`
- `a` AND `b` AND `c`
- `a` AND `b` AND `c` with range on `c`

It CANNOT efficiently serve queries on `b` alone, `c` alone, or `b AND c`.

**Column ordering strategy**:
1. **Equality columns first**: Put columns with `=` conditions before columns with range conditions (`>`, `<`, `BETWEEN`)
2. **Most selective equality columns first** (marginal benefit, but helps with skip-scan patterns in newer Postgres)

```sql
-- Query: WHERE tenant_id = ? AND status = ? AND created_at > ?
-- Optimal index:
CREATE INDEX idx_orders_tenant_status_created
    ON orders (tenant_id, status, created_at);
-- tenant_id (equality, first) → status (equality, second) → created_at (range, last)
```

#### Covering Indexes

A **covering index** includes all columns the query needs, enabling an **index-only scan** — Postgres reads only the index and never touches the heap.

```sql
-- Query: SELECT id, amount FROM orders WHERE customer_id = ? AND status = 'shipped'
-- This index covers the query:
CREATE INDEX idx_orders_covering
    ON orders (customer_id, status) INCLUDE (amount);
-- The INCLUDE columns are in the index leaf pages but not in the index tree structure
```

Index-only scans require the **visibility map** to confirm all tuples on a page are visible. Frequent updates to a table can cause the visibility map to be incomplete, forcing Postgres to check the heap anyway. Run VACUUM frequently on these tables.

#### Partial Indexes

Index only the rows you actually query:

```sql
-- Only index active users (80% of queries filter by active)
CREATE INDEX idx_users_active_email ON users (email) WHERE active = true;
-- This index is smaller, faster to scan, and faster to maintain

-- Only index unprocessed orders
CREATE INDEX idx_orders_unprocessed ON orders (created_at) WHERE processed_at IS NULL;
-- As orders get processed, they fall out of the index — it stays small

-- Only index recent data
CREATE INDEX idx_events_recent ON events (created_at, type)
    WHERE created_at > '2025-01-01';
-- Periodically recreate with a newer date to keep it small
```

#### Expression Indexes

```sql
-- Index on a computed expression
CREATE INDEX idx_users_email_lower ON users (LOWER(email));
-- Now: WHERE LOWER(email) = 'alice@example.com' uses the index

-- Index on JSONB field
CREATE INDEX idx_events_type ON events ((payload->>'type'));
-- Now: WHERE payload->>'type' = 'click' uses the index

-- Index on date extraction
CREATE INDEX idx_orders_month ON orders (date_trunc('month', created_at));
-- Now: WHERE date_trunc('month', created_at) = '2025-06-01' uses the index
```

#### Monitoring Index Usage

```sql
-- Unused indexes (candidates for removal)
SELECT schemaname, relname, indexrelname, idx_scan,
       pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE '%_pkey'   -- Don't drop primary keys
ORDER BY pg_relation_size(indexrelid) DESC;

-- Tables with too many sequential scans (might need an index)
SELECT schemaname, relname, seq_scan, seq_tup_read,
       idx_scan, idx_tup_fetch,
       CASE WHEN seq_scan > 0
            THEN round(seq_tup_read::numeric / seq_scan)
            ELSE 0 END AS avg_tuples_per_seq_scan
FROM pg_stat_user_tables
WHERE seq_scan > 100
ORDER BY seq_tup_read DESC
LIMIT 20;
-- High avg_tuples_per_seq_scan on a large table = missing index

-- Duplicate indexes (exact duplicates waste space and write overhead)
SELECT array_agg(indexname) AS indexes, tablename, indexdef
FROM pg_indexes
GROUP BY tablename, indexdef
HAVING count(*) > 1;

-- Index bloat estimation
SELECT schemaname, tablename, indexname,
       pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
       idx_scan
FROM pg_stat_user_indexes
JOIN pg_index ON pg_index.indexrelid = pg_stat_user_indexes.indexrelid
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 20;
-- Compare index_size with expected size. Rebuild with REINDEX CONCURRENTLY if bloated.
```

---

## 5. Connection Management

### 5.1 Why Connections Are Expensive

PostgreSQL forks a **new OS process** for every client connection. Each process:
- Consumes 5-10 MB of RAM (stack, local caches, work_mem allocations)
- Has its own entry in the process table
- Requires context switching between processes (expensive on high-connection-count systems)

At 500 connections, you're consuming 2.5-5 GB of RAM just for connection overhead — before any queries run. At 1000+, the context switching overhead dominates and throughput actually decreases. This is counterintuitive: **more connections = slower throughput** beyond a certain point.

The optimal number of active connections for maximum throughput is surprisingly small:

```
connections = (core_count * 2) + effective_spindle_count
```

For an 8-core server with SSD: (8 * 2) + 1 = 17 connections. Yes, 17. More than this causes contention rather than parallelism.

### 5.2 Connection Pooling

**PgBouncer** is the standard solution. It sits between your application and Postgres, multiplexing many client connections onto a small pool of actual database connections.

```
Application (500 connections) → PgBouncer (pool of 20 connections) → PostgreSQL
```

#### PgBouncer Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Transaction pooling** | Connection is assigned for the duration of a transaction, then returned to the pool | Most applications (recommended default) |
| **Session pooling** | Connection is assigned for the duration of the client session | Applications that use session-level features (SET, prepared statements, LISTEN/NOTIFY) |
| **Statement pooling** | Connection is assigned for a single statement | Only for simple autocommit workloads |

Transaction pooling is the sweet spot for most applications. But it breaks anything that depends on session state:
- `SET` commands (search_path, work_mem)
- Named prepared statements
- `LISTEN/NOTIFY`
- Temporary tables
- Advisory locks

```ini
# pgbouncer.ini
[databases]
mydb = host=localhost port=5432 dbname=mydb

[pgbouncer]
pool_mode = transaction
default_pool_size = 20          # Connections per user/database pair
max_client_conn = 1000          # Max client connections to PgBouncer
reserve_pool_size = 5           # Extra connections for burst handling
reserve_pool_timeout = 3        # Seconds before reserve connections are used
server_idle_timeout = 600       # Close idle server connections after 10 min
```

### 5.3 Prepared Statements and Connection Pooling

Transaction pooling and prepared statements don't mix because prepared statements are session-scoped. When PgBouncer reassigns a server connection to a new client, that client's prepared statements don't exist on the new connection.

Solutions:
- Use `DEALLOCATE ALL` at transaction start (some ORMs do this automatically)
- Use PgBouncer's `server_reset_query = DISCARD ALL` (runs on every connection return)
- Use PgBouncer 1.21+ with **prepared statement support** (transparent re-preparation)

### 5.4 Serverless Connection Challenges

Serverless functions (AWS Lambda, Vercel Functions) create a new connection per cold start and may have thousands of concurrent instances. Without mitigation, this quickly exhausts Postgres connection limits.

```
Lambda (3000 concurrent instances) → Direct Postgres (max_connections=100) → CRASH
```

**Solutions**:

1. **AWS RDS Proxy**: Managed connection pooler built for Lambda → RDS. Handles connection multiplexing, credential rotation, and failover.

```
Lambda → RDS Proxy (pools connections) → RDS PostgreSQL
```

2. **Neon Serverless Driver**: For Neon Postgres, their serverless driver uses HTTP/WebSocket instead of persistent TCP connections.

3. **Supabase Supavisor**: Managed PgBouncer built into Supabase.

4. **Self-hosted PgBouncer**: Deploy PgBouncer on an EC2 instance between Lambda and RDS.

---

## 6. Backup, Recovery & High Availability

### 6.1 Logical Backups

```bash
# Dump a single database (SQL format)
pg_dump -d mydb -f backup.sql

# Dump with compression (custom format — recommended)
pg_dump -d mydb -Fc -f backup.dump

# Dump specific tables
pg_dump -d mydb -t orders -t customers -Fc -f partial.dump

# Dump all databases and roles
pg_dumpall -f full_cluster.sql

# Restore custom format dump
pg_restore -d mydb -Fc backup.dump

# Parallel restore (4 jobs)
pg_restore -d mydb -Fc -j 4 backup.dump
```

**Pros**: Portable across Postgres versions, can dump/restore individual tables, human-readable SQL format available.
**Cons**: Slow for large databases (serializes all data through SQL), must hold a snapshot for the entire dump duration (blocking vacuum on touched data).

### 6.2 Physical Backups

Physical backups copy the raw data files, which is much faster for large databases.

```bash
# pg_basebackup: Built-in physical backup
pg_basebackup -D /backup/base -Ft -Xs -P -R
# -Ft: tar format
# -Xs: Stream WAL during backup (ensures consistency)
# -P: Show progress
# -R: Write recovery configuration (standby.signal + primary_conninfo)
```

**pgBackRest** (production-grade backup tool):
```bash
# Configure: /etc/pgbackrest/pgbackrest.conf
[mydb]
pg1-path=/var/lib/postgresql/16/main

[global]
repo1-path=/backup/pgbackrest
repo1-retention-full=2
repo1-retention-diff=7
compress-type=zst
process-max=4

# Full backup
pgbackrest --stanza=mydb backup --type=full

# Incremental backup
pgbackrest --stanza=mydb backup --type=incr

# Restore to a point in time
pgbackrest --stanza=mydb restore --type=time \
    --target="2026-03-23 14:30:00" \
    --target-action=promote
```

**WAL-G** (cloud-native backup tool):
```bash
# Backup to S3
export WALG_S3_PREFIX=s3://my-bucket/wal-g-backup
wal-g backup-push /var/lib/postgresql/16/main

# List backups
wal-g backup-list

# Restore latest
wal-g backup-fetch /restore/path LATEST
```

### 6.3 Point-in-Time Recovery (PITR)

PITR lets you recover to any specific moment — not just when the backup was taken. This is critical for recovering from accidental `DROP TABLE` or `DELETE` without `WHERE`.

**Mechanism**: Base backup + replay WAL from that backup's start to the target time.

```
Timeline:
  Day 1: Full backup taken at 00:00
  Day 1-3: WAL segments archived continuously
  Day 3, 14:30: Accidental DELETE happens
  Recovery target: Day 3, 14:29:59

  Restore: Base backup (Day 1) + all WAL from Day 1 to Day 3 14:29:59
```

### 6.4 Streaming Replication

```
Primary (reads + writes)
    │
    ├── WAL stream ──→ Standby 1 (read-only queries)
    │
    └── WAL stream ──→ Standby 2 (read-only queries)
```

**Synchronous vs Asynchronous**:
- **Async** (default): Primary doesn't wait for standby to confirm WAL receipt. Fastest, but standby can be slightly behind. On primary failure, you lose uncommitted transactions that weren't replicated.
- **Sync**: Primary waits for at least one standby to confirm WAL write. Zero data loss, but adds latency to every commit (network round-trip to standby).

```sql
-- Primary: Enable synchronous replication
ALTER SYSTEM SET synchronous_standby_names = 'FIRST 1 (standby1, standby2)';
-- FIRST 1: Wait for at least 1 of the listed standbys
```

### 6.5 Automatic Failover

When the primary fails, a standby must be promoted. Manual failover is simple but slow (requires human intervention). Automatic failover tools:

- **Patroni**: The standard for HA PostgreSQL. Uses a distributed consensus store (etcd, ZooKeeper, Consul) to manage leader election. Handles promotion, fencing, and configuration management.
- **pg_auto_failover**: Simpler alternative from Citus/Microsoft. Uses a monitor node for health checks and failover decisions.

```yaml
# Patroni configuration (simplified)
scope: mydb-cluster
namespace: /service/
name: node1

restapi:
  listen: 0.0.0.0:8008

etcd:
  hosts: etcd1:2379,etcd2:2379,etcd3:2379

postgresql:
  listen: 0.0.0.0:5432
  data_dir: /var/lib/postgresql/16/main
  parameters:
    max_connections: 100
    shared_buffers: 16GB
```

### 6.6 Logical Replication

Unlike streaming replication (which copies the entire WAL), logical replication works at the table level and can selectively replicate specific tables.

```sql
-- On the publisher (source)
CREATE PUBLICATION my_pub FOR TABLE orders, customers;

-- On the subscriber (destination)
CREATE SUBSCRIPTION my_sub
    CONNECTION 'host=source_host port=5432 dbname=mydb'
    PUBLICATION my_pub;
```

Use cases:
- Replicating a subset of tables to an analytics database
- Major version upgrades (replicate from old version to new version, then switch)
- Multi-database aggregation

### 6.7 RDS/Aurora Specifics

AWS manages much of this for you, but understanding what happens under the hood helps:

- **Automated backups**: RDS takes daily snapshots + continuously archives WAL to S3. Retention: 1-35 days.
- **Multi-AZ**: Synchronous replication to a standby in another AZ. Automatic failover in ~60 seconds (DNS update).
- **Aurora**: Storage is decoupled — 6 copies across 3 AZs at the storage layer. WAL records are sent directly to the storage layer (no full page writes needed). Faster crash recovery, automatic storage scaling.
- **Aurora Read Replicas**: Share the same storage volume as the primary — no replication lag for data (but may have query-level lag). Promotion is nearly instant.

---

## 7. Database Performance Tuning

### 7.1 PostgreSQL Configuration Cheat Sheet

For a dedicated database server with 64 GB RAM, 16 cores, SSD storage:

```ini
# Memory
shared_buffers = 16GB                  # 25% of RAM
effective_cache_size = 48GB            # 75% of RAM
work_mem = 64MB                        # Careful: per-operation, per-connection
maintenance_work_mem = 2GB             # For VACUUM, CREATE INDEX
huge_pages = try                       # Reduce TLB misses

# Connections
max_connections = 100                  # Keep low, use PgBouncer
superuser_reserved_connections = 3

# WAL
wal_level = replica
max_wal_senders = 5
wal_buffers = 64MB
max_wal_size = 4GB                     # Higher = less frequent checkpoints
min_wal_size = 1GB
checkpoint_completion_target = 0.9

# Planner
random_page_cost = 1.1                 # SSD: nearly same as sequential
effective_io_concurrency = 200         # SSD: high parallelism
default_statistics_target = 100        # Increase for complex distributions

# Autovacuum
autovacuum_max_workers = 4
autovacuum_vacuum_cost_delay = 2ms
autovacuum_vacuum_cost_limit = 400     # Higher than default for fast cleanup

# Parallelism
max_worker_processes = 16
max_parallel_workers_per_gather = 4
max_parallel_workers = 16
max_parallel_maintenance_workers = 4    # For parallel CREATE INDEX

# Timeouts
statement_timeout = '30s'                        # Kill runaway queries
idle_in_transaction_session_timeout = '5min'      # Kill idle transactions
lock_timeout = '10s'                              # Don't wait forever for locks

# Logging
log_min_duration_statement = 1000      # Log queries taking > 1 second
log_checkpoints = on
log_lock_waits = on
log_temp_files = 0                     # Log any temp file creation
```

### 7.2 Monitoring Queries

#### pg_stat_statements (The Most Important Extension)

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Top 20 queries by total execution time
SELECT
    substr(query, 1, 100) AS query_preview,
    calls,
    round(total_exec_time::numeric, 2) AS total_time_ms,
    round(mean_exec_time::numeric, 2) AS avg_time_ms,
    round((100 * total_exec_time / sum(total_exec_time) OVER ())::numeric, 2) AS pct_total,
    rows
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;
-- Focus on queries with highest total_time (calls * avg_time)
-- A query taking 5ms but called 1M times dominates a query taking 5s called once

-- Top queries by I/O (shared blocks read = cache misses)
SELECT
    substr(query, 1, 100) AS query_preview,
    calls,
    shared_blks_hit,
    shared_blks_read,
    round(shared_blks_hit::numeric / NULLIF(shared_blks_hit + shared_blks_read, 0) * 100, 2) AS cache_hit_pct
FROM pg_stat_statements
ORDER BY shared_blks_read DESC
LIMIT 20;

-- Reset statistics (do this after optimization to re-baseline)
SELECT pg_stat_statements_reset();
```

#### pg_stat_activity (What's Running Right Now)

```sql
-- Currently running queries
SELECT pid, now() - query_start AS duration, state, wait_event_type, wait_event,
       substr(query, 1, 200) AS query
FROM pg_stat_activity
WHERE state = 'active' AND pid != pg_backend_pid()
ORDER BY query_start;

-- Blocked queries (waiting for locks)
SELECT blocked.pid AS blocked_pid,
       blocked.query AS blocked_query,
       blocking.pid AS blocking_pid,
       blocking.query AS blocking_query,
       now() - blocked.query_start AS blocked_duration
FROM pg_stat_activity blocked
JOIN pg_locks blocked_locks ON blocked.pid = blocked_locks.pid AND NOT blocked_locks.granted
JOIN pg_locks blocking_locks ON blocked_locks.locktype = blocking_locks.locktype
    AND blocked_locks.relation = blocking_locks.relation
    AND blocking_locks.granted
JOIN pg_stat_activity blocking ON blocking_locks.pid = blocking.pid
WHERE blocked.pid != blocking.pid;

-- Idle-in-transaction connections (potential vacuum blockers)
SELECT pid, now() - xact_start AS xact_duration, state, query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY xact_start;
```

#### pg_stat_user_tables

```sql
-- Table health overview
SELECT schemaname, relname,
       seq_scan, seq_tup_read,
       idx_scan, idx_tup_fetch,
       n_tup_ins, n_tup_upd, n_tup_del,
       n_live_tup, n_dead_tup,
       round(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 1) AS dead_pct,
       last_vacuum, last_autovacuum, last_analyze, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 20;
```

#### Lock Monitoring

```sql
-- Current locks with human-readable information
SELECT l.pid, l.locktype, l.mode, l.granted,
       l.relation::regclass AS table_name,
       a.state, a.query
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE l.relation IS NOT NULL
ORDER BY l.relation, l.pid;
```

### 7.3 Common Performance Problems and Solutions

#### Problem: Bloated Tables

**Symptoms**: Table size much larger than expected, seq scans getting slower, `n_dead_tup` is high.

**Diagnosis**:
```sql
-- Check dead tuple ratio
SELECT relname, n_live_tup, n_dead_tup,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY n_dead_tup DESC;

-- Estimate bloat using pgstattuple
CREATE EXTENSION IF NOT EXISTS pgstattuple;
SELECT * FROM pgstattuple('your_table');
-- dead_tuple_percent > 20% is problematic
```

**Fix**: Tune autovacuum for the affected tables. If already bloated, use `pg_repack` to rewrite online.

#### Problem: Lock Contention

**Symptoms**: Queries waiting for locks, application timeouts, `wait_event_type = 'Lock'`.

**Diagnosis**: Use the blocked queries query above.

**Common causes**:
- Long-running transactions holding row locks → set `idle_in_transaction_session_timeout`
- DDL operations (ALTER TABLE) taking ACCESS EXCLUSIVE lock → use CONCURRENTLY variants
- Missing indexes causing unnecessary row-level lock escalation
- `SELECT ... FOR UPDATE` held too long → minimize time in transaction

#### Problem: Connection Exhaustion

**Symptoms**: "FATAL: too many connections for role" errors, application connection timeouts.

```sql
-- Current connection count
SELECT count(*), state FROM pg_stat_activity GROUP BY state;

-- Connections by application
SELECT application_name, count(*) FROM pg_stat_activity GROUP BY application_name ORDER BY count DESC;
```

**Fix**: Deploy PgBouncer. Reduce `max_connections` (counterintuitively, this often improves throughput). Ensure application code properly closes connections and doesn't leak them.

#### Problem: Checkpoint Storms

**Symptoms**: Periodic I/O spikes every few minutes, `pg_stat_bgwriter` shows many buffers written per checkpoint.

```sql
SELECT checkpoints_timed, checkpoints_req,
       buffers_checkpoint, buffers_clean, buffers_backend,
       maxwritten_clean
FROM pg_stat_bgwriter;
-- buffers_backend > 0 means the backend (your query) had to write dirty pages itself
-- because the background writer couldn't keep up — this is bad
-- checkpoints_req > checkpoints_timed means WAL is filling up too fast
```

**Fix**: Increase `max_wal_size` (allows more WAL before forced checkpoint), increase `checkpoint_completion_target` (spreads the I/O), adjust `bgwriter_lru_maxpages` and `bgwriter_lru_multiplier`.

#### Problem: Disk I/O Bottleneck

**Symptoms**: High `shared_blks_read` in pg_stat_statements, low cache hit ratio, high iowait in system metrics.

**Fix**:
1. Increase `shared_buffers` if below 25% of RAM
2. Ensure `random_page_cost` is set correctly for your storage
3. Add indexes to reduce the number of pages read
4. Use covering indexes for index-only scans
5. Consider partitioning large tables so queries only scan relevant partitions
6. Move to faster storage (NVMe SSD)

---

## 8. Database Management & Operations

### 8.1 Schema Migration Strategies

#### Expand-and-Contract Pattern (Zero-Downtime Migrations)

Never make breaking changes in a single step. Instead:

1. **Expand**: Add the new column/table alongside the old one
2. **Migrate**: Backfill data, update application to write to both old and new
3. **Contract**: Remove the old column/table after all code is deployed

```sql
-- Example: Renaming a column (name → full_name)

-- Step 1: Add new column (non-blocking)
ALTER TABLE users ADD COLUMN full_name text;

-- Step 2: Backfill (in batches to avoid long locks)
UPDATE users SET full_name = name WHERE id BETWEEN 1 AND 100000;
UPDATE users SET full_name = name WHERE id BETWEEN 100001 AND 200000;
-- ... or use a background job

-- Step 3: Deploy code that writes to both name AND full_name
-- Step 4: Deploy code that reads from full_name
-- Step 5: Deploy code that stops writing to name

-- Step 6: Drop old column (after verifying no code reads it)
ALTER TABLE users DROP COLUMN name;
```

#### Dangerous Operations and Safe Alternatives

| Dangerous | Why | Safe Alternative |
|-----------|-----|-----------------|
| `ALTER TABLE ADD COLUMN ... DEFAULT x` (PG < 11) | Rewrites entire table | PG 11+: safe, uses metadata-only default |
| `ALTER TABLE ... SET NOT NULL` | Scans entire table to validate | Add CHECK constraint as NOT VALID, then VALIDATE separately |
| `CREATE INDEX` | Locks table for writes | `CREATE INDEX CONCURRENTLY` |
| `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY` | Locks both tables | Add as NOT VALID, then VALIDATE CONSTRAINT separately |
| `ALTER TABLE ... ALTER COLUMN TYPE` | Rewrites table | Add new column, migrate, drop old |

```sql
-- Safe NOT NULL constraint
ALTER TABLE orders ADD CONSTRAINT orders_status_not_null
    CHECK (status IS NOT NULL) NOT VALID;
-- This returns immediately — no table scan

-- Later, validate the constraint (scans table but doesn't block writes)
ALTER TABLE orders VALIDATE CONSTRAINT orders_status_not_null;
-- After validation, the constraint is equivalent to NOT NULL

-- Safe index creation
CREATE INDEX CONCURRENTLY idx_orders_customer ON orders (customer_id);
-- This doesn't lock the table but takes longer and requires more I/O
-- If it fails partway, it leaves an INVALID index — drop and retry
```

### 8.2 Partitioning

Partitioning splits a large table into smaller physical tables (partitions) while presenting a single logical table to queries.

#### When to Partition

- Table has hundreds of millions of rows and most queries filter on a specific column (date, tenant_id)
- You need to efficiently drop old data (detach partition instead of DELETE)
- Maintenance operations (VACUUM, REINDEX) take too long on the full table

#### Types

```sql
-- Range partitioning (most common — by date)
CREATE TABLE events (
    id bigserial,
    created_at timestamptz NOT NULL,
    type text,
    payload jsonb
) PARTITION BY RANGE (created_at);

CREATE TABLE events_2025_q1 PARTITION OF events
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE events_2025_q2 PARTITION OF events
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE events_2025_q3 PARTITION OF events
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE events_2025_q4 PARTITION OF events
    FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');

-- List partitioning (by category)
CREATE TABLE orders (
    id bigserial,
    region text NOT NULL,
    amount numeric
) PARTITION BY LIST (region);

CREATE TABLE orders_us PARTITION OF orders FOR VALUES IN ('US');
CREATE TABLE orders_eu PARTITION OF orders FOR VALUES IN ('EU', 'UK');
CREATE TABLE orders_apac PARTITION OF orders FOR VALUES IN ('JP', 'AU', 'SG');

-- Hash partitioning (even distribution)
CREATE TABLE sessions (
    id uuid NOT NULL,
    data jsonb
) PARTITION BY HASH (id);

CREATE TABLE sessions_0 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE sessions_1 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE sessions_2 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE sessions_3 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 3);
```

#### Partition Pruning

The query planner automatically skips partitions that can't contain matching rows:

```sql
EXPLAIN SELECT * FROM events WHERE created_at = '2025-06-15';
-- Only scans events_2025_q2, skips all other partitions
```

Ensure `enable_partition_pruning = on` (default).

#### Archiving with Partitions

```sql
-- Instead of DELETE FROM events WHERE created_at < '2024-01-01':
-- (which would scan and delete millions of rows, generating dead tuples)

-- Detach the old partition (instant, metadata-only)
ALTER TABLE events DETACH PARTITION events_2023_q4;

-- Optionally drop it (instant, reclaims disk space)
DROP TABLE events_2023_q4;

-- Or move it to cheap storage:
ALTER TABLE events_2023_q4 SET TABLESPACE cold_storage;
```

**pg_partman**: Extension that automates partition creation and retention:
```sql
CREATE EXTENSION pg_partman;

SELECT partman.create_parent(
    p_parent_table => 'public.events',
    p_control => 'created_at',
    p_type => 'native',
    p_interval => 'monthly',
    p_premake => 3          -- Pre-create 3 future partitions
);

-- Configure retention (automatically drop partitions older than 12 months)
UPDATE partman.part_config
SET retention = '12 months', retention_keep_table = false
WHERE parent_table = 'public.events';
```

### 8.3 Monitoring and Alerting

What to alert on:

| Metric | Warning | Critical | Why |
|--------|---------|----------|-----|
| Connection count | > 80% of max_connections | > 90% | Connection exhaustion imminent |
| Replication lag (bytes) | > 100 MB | > 1 GB | Standby falling behind, data loss risk |
| Dead tuples ratio | > 10% | > 30% | Vacuum not keeping up, bloat growing |
| Transaction ID age | > 500M | > 1B | Wraparound approaching |
| Long-running queries | > 5 min | > 30 min | Resource hogging, lock holding |
| Idle-in-transaction | > 5 min | > 30 min | Blocks vacuum, holds locks |
| Disk usage | > 75% | > 90% | Out of disk = database crash |
| Cache hit ratio | < 99% | < 95% | Working set doesn't fit in memory |
| Checkpoint frequency | > 1/min | > 5/min | WAL size too small, I/O storms |
| Temp file creation | Any | Large/frequent | work_mem too low, queries spilling to disk |

### 8.4 Capacity Planning

```sql
-- Table growth rate (requires pg_stat_statements or periodic snapshots)
-- Snapshot table sizes weekly and compute growth rate

-- Current table sizes
SELECT schemaname, relname,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
       pg_size_pretty(pg_table_size(relid)) AS table_size,
       pg_size_pretty(pg_indexes_size(relid)) AS index_size,
       n_live_tup
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 20;

-- Database size
SELECT pg_size_pretty(pg_database_size('mydb'));

-- Project disk needs:
-- If table grows 10 GB/month, and you have 500 GB disk:
-- At 75% (375 GB) usage with 200 GB used today:
-- (375 - 200) / 10 = 17.5 months until warning threshold
```

### 8.5 Database Upgrade Strategies

#### Minor Version Upgrades (e.g., 16.1 → 16.3)

Binary compatible. Simply replace binaries and restart. Always apply these — they contain security and bug fixes.

```bash
# On Debian/Ubuntu
sudo apt-get update && sudo apt-get install postgresql-16
sudo systemctl restart postgresql
```

#### Major Version Upgrades (e.g., 15 → 16)

Options:

1. **pg_upgrade** (fastest): Converts data files in place. Requires brief downtime.
```bash
# Stop old server
pg_ctlcluster 15 main stop

# Run pg_upgrade
/usr/lib/postgresql/16/bin/pg_upgrade \
    --old-datadir=/var/lib/postgresql/15/main \
    --new-datadir=/var/lib/postgresql/16/main \
    --old-bindir=/usr/lib/postgresql/15/bin \
    --new-bindir=/usr/lib/postgresql/16/bin \
    --link    # Hard-link files instead of copying (much faster)

# Start new server
pg_ctlcluster 16 main start

# Run recommended post-upgrade steps
./analyze_new_cluster.sh    # Update statistics
./delete_old_cluster.sh     # Clean up (after verification)
```

2. **Logical replication** (minimal downtime): Set up logical replication from old to new version, let it catch up, then switch.
```sql
-- On PG 15 (source)
CREATE PUBLICATION upgrade_pub FOR ALL TABLES;

-- On PG 16 (target, with schema already created via pg_dump --schema-only)
CREATE SUBSCRIPTION upgrade_sub
    CONNECTION 'host=old_server dbname=mydb'
    PUBLICATION upgrade_pub;

-- Monitor replication lag, and when caught up:
-- 1. Stop writes to old server
-- 2. Verify subscription is caught up
-- 3. Point application to new server
-- 4. Drop subscription and publication
```

3. **Dump and restore** (simplest, most downtime): `pg_dump` from old, `pg_restore` to new. Suitable for small databases where downtime is acceptable.

---

## Summary: The Database Performance Debugging Flowchart

When someone says "the database is slow," work through this checklist:

```
1. IDENTIFY THE SLOW QUERY
   └→ pg_stat_statements: Sort by total_exec_time
   └→ pg_stat_activity: Check currently running queries
   └→ Application logs / APM tool

2. ANALYZE THE QUERY PLAN
   └→ EXPLAIN (ANALYZE, BUFFERS) the query
   └→ Compare estimated vs actual rows (statistics stale?)
   └→ Look for Seq Scans on large tables, Nested Loops with high loops
   └→ Check Buffers: shared read (cache misses)

3. CHECK FOR MISSING INDEXES
   └→ pg_stat_user_tables: high seq_scan count?
   └→ EXPLAIN output: "Rows Removed by Filter" high?
   └→ Add appropriate index (composite? partial? covering?)

4. CHECK FOR TABLE BLOAT
   └→ pg_stat_user_tables: n_dead_tup high?
   └→ Is autovacuum running? Last autovacuum time?
   └→ Any long-running transactions blocking vacuum?
   └→ Tune autovacuum settings for the table

5. CHECK FOR LOCK CONTENTION
   └→ pg_locks + pg_stat_activity: queries waiting?
   └→ Identify the blocking query/transaction
   └→ Reduce transaction duration, add indexes to reduce lock scope

6. CHECK SYSTEM RESOURCES
   └→ CPU: parallel query saturation? Too many connections?
   └→ Memory: cache hit ratio? work_mem spilling to disk?
   └→ Disk I/O: checkpoint storms? Random reads?
   └→ Connections: exhaustion? Need pooler?

7. CHECK CONFIGURATION
   └→ random_page_cost correct for storage type?
   └→ shared_buffers and effective_cache_size sized properly?
   └→ work_mem appropriate for workload?
   └→ Autovacuum settings tuned for write volume?
```

## 9. SQL Mastery

The queries that separate junior from senior database engineers. These are the patterns you'll use weekly.

### Common Table Expressions (CTEs)

```sql
-- Basic CTE: readable, named subqueries
WITH active_users AS (
    SELECT id, name, email, created_at
    FROM users
    WHERE status = 'active' AND last_login > NOW() - INTERVAL '30 days'
),
user_orders AS (
    SELECT user_id, COUNT(*) as order_count, SUM(total) as total_spent
    FROM orders
    WHERE created_at > NOW() - INTERVAL '30 days'
    GROUP BY user_id
)
SELECT au.name, au.email, COALESCE(uo.order_count, 0) as orders,
       COALESCE(uo.total_spent, 0) as spent
FROM active_users au
LEFT JOIN user_orders uo ON au.id = uo.user_id
ORDER BY uo.total_spent DESC NULLS LAST;

-- WHY CTEs: readable, self-documenting, can reference multiple times
-- NOTE: In PostgreSQL, CTEs are optimization fences before v12.
-- In v12+, the planner can inline CTEs (use MATERIALIZED to force old behavior)
```

### Recursive CTEs

```sql
-- Organizational hierarchy (find all reports under a manager)
WITH RECURSIVE org_tree AS (
    -- Base case: the starting manager
    SELECT id, name, manager_id, 0 as depth
    FROM employees
    WHERE id = 42  -- starting manager

    UNION ALL

    -- Recursive case: find direct reports of current level
    SELECT e.id, e.name, e.manager_id, ot.depth + 1
    FROM employees e
    JOIN org_tree ot ON e.manager_id = ot.id
    WHERE ot.depth < 10  -- safety limit to prevent infinite recursion
)
SELECT * FROM org_tree ORDER BY depth, name;

-- Category tree (e-commerce: Electronics > Phones > Smartphones)
-- Bill of materials (manufacturing: assembly contains sub-assemblies)
-- Graph traversal in SQL (shortest path, reachability)
```

### Window Functions

```sql
-- ROW_NUMBER: assign a unique number within each partition
SELECT name, department, salary,
    ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) as rank
FROM employees;
-- Use case: "top N per group" → WHERE rank <= 3

-- RANK vs DENSE_RANK vs ROW_NUMBER
-- Salaries: 100, 90, 90, 80
-- ROW_NUMBER: 1, 2, 3, 4  (always unique)
-- RANK:       1, 2, 2, 4  (gaps after ties)
-- DENSE_RANK: 1, 2, 2, 3  (no gaps)

-- Running total
SELECT date, revenue,
    SUM(revenue) OVER (ORDER BY date) as running_total
FROM daily_revenue;

-- Moving average (7-day)
SELECT date, revenue,
    AVG(revenue) OVER (
        ORDER BY date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as avg_7day
FROM daily_revenue;

-- Percentage of total
SELECT department, salary,
    salary::numeric / SUM(salary) OVER () * 100 as pct_of_total
FROM employees;

-- LAG / LEAD (access previous/next row)
SELECT date, revenue,
    revenue - LAG(revenue) OVER (ORDER BY date) as day_over_day_change,
    LEAD(revenue) OVER (ORDER BY date) as next_day_revenue
FROM daily_revenue;

-- FIRST_VALUE / LAST_VALUE / NTH_VALUE
SELECT name, department, salary,
    FIRST_VALUE(name) OVER (PARTITION BY department ORDER BY salary DESC) as highest_paid
FROM employees;

-- NTILE (divide rows into N buckets)
SELECT name, salary,
    NTILE(4) OVER (ORDER BY salary) as quartile
FROM employees;
```

### JSON Operations (PostgreSQL)

```sql
-- JSONB storage and querying (PostgreSQL)
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert
INSERT INTO events (data) VALUES ('{"type": "click", "page": "/home", "user_id": 123}');

-- Access fields
SELECT data->>'type' as event_type,          -- text extraction
       data->'user_id' as user_id_json,       -- JSON extraction
       data#>>'{nested,deep,field}' as deep   -- nested path extraction
FROM events;

-- Filter on JSON fields
SELECT * FROM events WHERE data->>'type' = 'click';
SELECT * FROM events WHERE data @> '{"type": "click"}';  -- containment (uses GIN index!)
SELECT * FROM events WHERE data ? 'user_id';              -- key exists

-- GIN index for JSONB (essential for performance)
CREATE INDEX idx_events_data ON events USING GIN (data);
-- Supports: @>, ?, ?|, ?& operators

-- JSONB aggregation
SELECT data->>'type' as event_type, COUNT(*)
FROM events
GROUP BY data->>'type';

-- Build JSON in queries
SELECT json_build_object(
    'user', json_build_object('id', u.id, 'name', u.name),
    'orders', json_agg(json_build_object('id', o.id, 'total', o.total))
) as result
FROM users u
JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.name;

-- jsonb_path_query (SQL/JSON path — PostgreSQL 12+)
SELECT * FROM events
WHERE jsonb_path_exists(data, '$.tags[*] ? (@ == "urgent")');
```

### Advanced Query Patterns

```sql
-- UPSERT (INSERT ... ON CONFLICT)
INSERT INTO user_settings (user_id, key, value)
VALUES (123, 'theme', 'dark')
ON CONFLICT (user_id, key)
DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();

-- Batch upsert with UNNEST (PostgreSQL — much faster than individual inserts)
INSERT INTO metrics (name, value, recorded_at)
SELECT * FROM UNNEST(
    ARRAY['cpu', 'memory', 'disk'],
    ARRAY[45.2, 72.1, 55.0],
    ARRAY[NOW(), NOW(), NOW()]
)
ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value;

-- LATERAL JOIN (like a for-each loop in SQL)
-- "For each user, get their 3 most recent orders"
SELECT u.name, recent_orders.*
FROM users u
CROSS JOIN LATERAL (
    SELECT id, total, created_at
    FROM orders
    WHERE user_id = u.id
    ORDER BY created_at DESC
    LIMIT 3
) recent_orders;
-- WHY LATERAL: the subquery can reference columns from the outer query

-- FILTER clause (conditional aggregation — cleaner than CASE)
SELECT
    COUNT(*) as total_orders,
    COUNT(*) FILTER (WHERE status = 'completed') as completed,
    COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
    SUM(total) FILTER (WHERE status = 'completed') as completed_revenue
FROM orders
WHERE created_at > NOW() - INTERVAL '30 days';

-- GROUPING SETS / CUBE / ROLLUP (multiple aggregation levels in one query)
SELECT
    COALESCE(region, 'ALL') as region,
    COALESCE(product, 'ALL') as product,
    SUM(revenue) as total
FROM sales
GROUP BY GROUPING SETS (
    (region, product),  -- per region+product
    (region),           -- per region subtotal
    (product),          -- per product subtotal
    ()                  -- grand total
);

-- EXISTS vs IN vs JOIN for semi-joins
-- EXISTS is usually fastest for correlated checks:
SELECT * FROM users u
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id AND o.total > 1000);
-- Better than: WHERE id IN (SELECT user_id FROM orders WHERE total > 1000)
-- Because EXISTS short-circuits on first match

-- Generate series (useful for filling gaps in time-series data)
SELECT date, COALESCE(daily.count, 0) as count
FROM generate_series(
    '2024-01-01'::date,
    '2024-01-31'::date,
    '1 day'::interval
) as date
LEFT JOIN (
    SELECT DATE(created_at) as day, COUNT(*) as count
    FROM events GROUP BY DATE(created_at)
) daily ON date = daily.day;
```

### Performance Patterns

```sql
-- Keyset pagination (fast, stable — replaces OFFSET for deep pages)
-- First page:
SELECT id, name, created_at FROM users ORDER BY created_at DESC, id DESC LIMIT 20;
-- Next page (pass last row's values):
SELECT id, name, created_at FROM users
WHERE (created_at, id) < ('2024-01-15T10:00:00Z', 12345)
ORDER BY created_at DESC, id DESC LIMIT 20;
-- WHY: uses index directly, O(1) regardless of page depth
-- vs OFFSET 10000 which must scan and discard 10000 rows

-- Materialized view for expensive aggregations
CREATE MATERIALIZED VIEW monthly_revenue AS
SELECT DATE_TRUNC('month', created_at) as month,
       SUM(total) as revenue, COUNT(*) as order_count
FROM orders GROUP BY 1;
-- Refresh: REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_revenue;
-- Requires unique index for CONCURRENTLY

-- Advisory locks (application-level distributed locking in PostgreSQL)
SELECT pg_try_advisory_lock(hashtext('process-invoices'));
-- Returns true if lock acquired, false if already held
-- Use for: singleton job execution, preventing duplicate processing
SELECT pg_advisory_unlock(hashtext('process-invoices'));
```

---

## 10. GRAPH DATABASES

When relationships between entities are as important as the entities themselves, relational JOINs become unwieldy and graph databases shine.

### How Graph Databases Work

**The Property Graph Model** (used by Neo4j, Neptune, Memgraph):
- **Nodes** (vertices): entities with labels and properties. `(:User {name: "Alice", age: 30})`
- **Relationships** (edges): typed, directed connections with properties. `[:FOLLOWS {since: "2023-01-15"}]`
- **Both nodes and relationships can have arbitrary key-value properties**
- Relationships are first-class citizens — they are stored and indexed, not computed via JOINs

**How it differs from relational:**
```
RELATIONAL: To find "friends of friends of Alice"
  SELECT DISTINCT f3.name
  FROM users u
  JOIN friendships f1 ON u.id = f1.user_id
  JOIN friendships f2 ON f1.friend_id = f2.user_id
  JOIN friendships f3_rel ON f2.friend_id = f3_rel.user_id
  JOIN users f3 ON f3_rel.friend_id = f3.id
  WHERE u.name = 'Alice';
  -- Multiple self-JOINs, gets worse with each hop, performance degrades

GRAPH (Cypher):
  MATCH (alice:User {name: "Alice"})-[:FRIENDS*2..3]-(fof:User)
  RETURN DISTINCT fof.name
  -- Traversal, not JOIN. Performance depends on local neighborhood size, not table size.
```

**Key insight:** In a relational DB, the cost of a JOIN is proportional to the table sizes. In a graph DB, the cost of a traversal is proportional to the local neighborhood — it doesn't matter if you have 1 billion nodes if you're only traversing 3 hops from one node.

### Query Languages

**Cypher** (Neo4j, Memgraph — most popular):
```cypher
-- Create nodes and relationships
CREATE (alice:User {name: "Alice", email: "alice@example.com"})
CREATE (bob:User {name: "Bob"})
CREATE (alice)-[:FOLLOWS {since: date("2024-01-15")}]->(bob)

-- Pattern matching: find who Alice follows
MATCH (alice:User {name: "Alice"})-[:FOLLOWS]->(followed)
RETURN followed.name

-- Variable-length paths: friends within 1-3 hops
MATCH (alice:User {name: "Alice"})-[:FRIENDS*1..3]-(friend)
RETURN DISTINCT friend.name, length(shortestPath((alice)-[:FRIENDS*]-(friend))) as distance

-- Shortest path
MATCH path = shortestPath((a:User {name: "Alice"})-[:KNOWS*]-(b:User {name: "Dave"}))
RETURN nodes(path), length(path)

-- Aggregation: most connected users
MATCH (u:User)-[:FOLLOWS]->(other)
RETURN u.name, count(other) as following_count
ORDER BY following_count DESC LIMIT 10

-- Subgraph pattern: find triangles (mutual connections)
MATCH (a:User)-[:FRIENDS]-(b:User)-[:FRIENDS]-(c:User)-[:FRIENDS]-(a)
RETURN DISTINCT a.name, b.name, c.name

-- Recommend: products bought by people who bought what I bought
MATCH (me:User {id: 123})-[:PURCHASED]->(product)<-[:PURCHASED]-(other)-[:PURCHASED]->(rec)
WHERE NOT (me)-[:PURCHASED]->(rec)
RETURN rec.name, count(other) as score
ORDER BY score DESC LIMIT 10
```

**Gremlin** (Apache TinkerPop — used by Neptune, JanusGraph, CosmosDB):
```groovy
// Traversal-based, more verbose, more portable
g.V().has('User', 'name', 'Alice').out('FOLLOWS').values('name')

// Variable-length: 2-3 hops
g.V().has('User', 'name', 'Alice').repeat(both('FRIENDS')).times(3).dedup().values('name')
```

**SPARQL** (RDF/triple stores — used by knowledge graphs, W3C standard):
```sparql
SELECT ?friendName WHERE {
  :alice :knows ?friend .
  ?friend :name ?friendName .
}
```

### When to Use a Graph Database

| Use Case | Why Graph Excels | Example |
|----------|-----------------|---------|
| **Social networks** | Relationship traversal IS the query | "People you may know", mutual friends, influence scoring |
| **Fraud detection** | Detect patterns across entities | Shared phone/email/device across accounts = fraud ring |
| **Recommendation engines** | Collaborative filtering via graph | "Customers who bought X also bought Y" — natural graph traversal |
| **Knowledge graphs** | Rich entity relationships with inference | Google Knowledge Panel, enterprise data catalogs |
| **Identity resolution** | Match entities across datasets | Same person with different names/emails across systems |
| **Network/IT operations** | Dependency mapping | "If this server goes down, what services are affected?" |
| **Authorization (ReBAC)** | Permission via relationships | Google Zanzibar: "User X has role Y on resource Z" — traverse the graph |
| **Supply chain** | Multi-hop dependency tracking | "Which suppliers are affected if factory X shuts down?" |

### When NOT to Use a Graph Database

- **Simple CRUD** with no relationship queries — Postgres is better
- **Heavy aggregations** (SUM, AVG, GROUP BY) — graph DBs are weak at this
- **Time-series data** — use TimescaleDB/InfluxDB
- **Full-text search** — use Elasticsearch
- **Tabular reporting** — relational is built for this
- **If your queries are always "get entity by ID"** — key-value store is simpler

### Graph Database Options

| Database | Model | Hosting | Best For |
|----------|-------|---------|----------|
| **Neo4j** | Property graph | Self-hosted, Aura (cloud) | Most mature, best tooling, Cypher |
| **Amazon Neptune** | Property graph + RDF | AWS managed | AWS-native, Gremlin + SPARQL |
| **Memgraph** | Property graph | Self-hosted, cloud | Real-time streaming graphs, Cypher-compatible |
| **ArangoDB** | Multi-model (graph + document + KV) | Self-hosted, cloud | When you need graph + document in one DB |
| **TigerGraph** | Property graph | Self-hosted, cloud | Massive-scale analytics, parallel traversal |
| **Dgraph** | Property graph (GraphQL-native) | Self-hosted, cloud | GraphQL API directly on the graph |
| **JanusGraph** | Property graph | Self-hosted (on Cassandra/HBase) | Massive scale, TinkerPop/Gremlin |
| **PostgreSQL + Apache AGE** | Property graph (extension) | Self-hosted | Add graph queries to existing Postgres |

### Data Modeling for Graphs

**Principles:**
1. **Model verbs as relationships, nouns as nodes.** "Alice PURCHASED Product" not "Alice has purchase_id 123"
2. **Use specific relationship types.** `:PURCHASED`, `:REVIEWED`, `:RETURNED` — not generic `:RELATED_TO`
3. **Store properties on relationships.** A `:PURCHASED` relationship can have `{date, quantity, price}`
4. **Avoid super-nodes** (nodes with millions of relationships). They become bottlenecks. Strategies: partition by time (`[:FOLLOWS_2024]`), use intermediate nodes
5. **Denormalize for query patterns.** Like NoSQL, model for how you query, not for normalization

**Example: E-Commerce Graph Model:**
```
(:Customer)-[:PURCHASED {date, amount}]->(:Order)-[:CONTAINS {qty}]->(:Product)
(:Product)-[:IN_CATEGORY]->(:Category)-[:SUBCATEGORY_OF]->(:Category)
(:Customer)-[:REVIEWED {rating, text}]->(:Product)
(:Customer)-[:VIEWED {timestamp}]->(:Product)
(:Product)-[:SIMILAR_TO {score}]->(:Product)
```

### Performance & Scaling

**Index everything you query by:** Create indexes on node properties used in MATCH patterns.
```cypher
CREATE INDEX FOR (u:User) ON (u.email)
CREATE INDEX FOR (u:User) ON (u.id)
CREATE CONSTRAINT FOR (u:User) REQUIRE u.id IS UNIQUE
```

**Scaling challenges:**
- Graph databases are harder to shard than key-value or document stores — sharding cuts edges, requiring cross-partition traversals
- **Neo4j**: leader-follower replication (reads scale, writes don't) or Fabric (sharded subgraphs)
- **Neptune**: read replicas (up to 15), storage auto-scales
- **JanusGraph/TigerGraph**: designed for horizontal scaling from the start

**Performance tips:**
- Limit traversal depth (`*1..5` not `*` — unbounded traversals can explode)
- Use `PROFILE` or `EXPLAIN` to understand query plans
- Warm the page cache on startup for frequently accessed subgraphs
- Batch writes (especially for initial data load — Neo4j's `LOAD CSV` or `neo4j-admin import`)

### Graph + Relational: Hybrid Architecture

Many production systems use BOTH:
```
PostgreSQL (OLTP)          Neo4j (Graph)
├── Users table            ├── (:User) nodes
├── Orders table           ├── (:Order) nodes
├── Products table         ├── Relationships
└── Transactions           └── Recommendations

Sync via CDC (Debezium) → Kafka → Neo4j consumer
```

- **Postgres** handles: CRUD, transactions, reporting, aggregations
- **Neo4j** handles: recommendations, fraud detection, social features, path finding
- **CDC keeps them in sync**: changes in Postgres are streamed to Neo4j

This is the most practical architecture for adding graph capabilities to an existing system — you don't replace your relational DB, you augment it.

---

This chapter covered the knowledge that separates engineers who can write SQL from engineers who can make databases perform. Every concept here — MVCC, WAL, vacuum, the query planner, buffer management — is something you will encounter in production. The difference between knowing these internals and not knowing them is the difference between spending 5 minutes diagnosing a problem and spending 5 days.
