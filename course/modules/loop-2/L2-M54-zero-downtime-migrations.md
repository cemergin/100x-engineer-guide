# L2-M54: Zero-Downtime Migrations

> **Loop 2 (Practice)** | Section 2D: Advanced Patterns | ⏱️ 60 min | 🟢 Core | Prerequisites: L2-M39 (Kubernetes Basics), familiarity with Postgres
>
> **Source:** Chapters 3, 22, 25, 32, 13 of the 100x Engineer Guide

> **Before you continue:** You need to rename a database column that three services depend on. If you deploy the schema change and the code change at the same time, there is a window where the old code runs against the new schema. How do you avoid that gap?

---

## The Goal

TicketPulse is adding assigned seating. The `tickets` table needs a `seat_number` column. The table has 10 million rows. The naive approach -- `ALTER TABLE tickets ADD COLUMN seat_number VARCHAR(10) NOT NULL DEFAULT 'GA'` -- locks the table for the duration of the operation. On a table with 10M rows, that could be minutes. During the lock, every ticket purchase, every order lookup, every event page that shows availability is blocked. Users see timeouts. Revenue is lost.

Zero-downtime migrations avoid this by breaking the migration into small, non-blocking steps. The application keeps running between each step.

**You will run code within the first two minutes.**

---

## 0. The Wrong Way (3 minutes)

See the problem first. On a test database with 10M rows:

```sql
-- Create a test table with 10M rows (do NOT run this on production)
CREATE TABLE tickets_test AS
  SELECT generate_series(1, 10000000) AS id, 'evt_1' AS event_id, 'active' AS status;

-- Time the naive migration
\timing on
ALTER TABLE tickets_test ADD COLUMN seat_number VARCHAR(10) NOT NULL DEFAULT 'GA';
-- On a typical server: 15-45 seconds of exclusive lock
```

During those 15-45 seconds, every query against this table blocks. In a production system with hundreds of concurrent requests, this causes a cascading failure.

**Rule: never run a blocking DDL statement on a table that serves live traffic.**

---

## 1. The Expand-and-Contract Pattern (5 minutes)

The idea: separate the migration into phases. Each phase is safe to run while the application is live.

```
Phase 1: EXPAND   — Add the column (nullable, no default) → instant, no lock
Phase 2: MIGRATE  — Deploy code that writes to the new column
Phase 3: BACKFILL — Fill existing rows in batches
Phase 4: CONTRACT — Add constraints, drop old code paths
```

Between each phase, the application is running normally. If any phase fails, you can stop and fix it without downtime.

---

## 2. Build: Phase 1 -- Add the Column (5 minutes)

```sql
-- Migration: 001_add_seat_number.sql
-- Phase 1: EXPAND

-- Adding a nullable column with no default is instant in Postgres.
-- It does NOT rewrite the table. It just updates the catalog.
ALTER TABLE tickets ADD COLUMN seat_number VARCHAR(10);

-- Verify: the column exists, is nullable, has no default
\d tickets
```

This runs in milliseconds regardless of table size. No lock. No rewrite.

> **Why nullable with no default?** Because:
> - `NOT NULL` without a default would fail (existing rows have no value)
> - `NOT NULL DEFAULT 'GA'` rewrites every row to set the default -- that is the lock
> - A nullable column with no default is a metadata-only change

**Try It:**

```bash
psql -d ticketpulse -c "ALTER TABLE tickets ADD COLUMN seat_number VARCHAR(10);"
# Should complete in < 10ms

# Verify the app still works
curl http://localhost:3000/api/events/evt_1/tickets
# Existing queries ignore the new column -- SELECT * still works
```

---

## 3. Build: Phase 2 -- Deploy New Code (10 minutes)

Before backfilling, deploy code that writes to the new column for new records. This ensures no new rows are created without a `seat_number`.

```typescript
// src/services/ticket.service.ts (updated)

async function issueTicket(
  orderId: string,
  eventId: string,
  tierId: string,
  seatNumber: string | null  // New parameter
): Promise<Ticket> {
  const result = await db.query(
    `INSERT INTO tickets (order_id, event_id, tier_id, status, seat_number)
     VALUES ($1, $2, $3, 'active', $4)
     RETURNING *`,
    [orderId, eventId, tierId, seatNumber || 'GA']  // Default to 'GA' for general admission
  );
  return result.rows[0];
}

// Reading code must handle NULL seat_number (from old rows)
async function getTicket(ticketId: string): Promise<Ticket> {
  const result = await db.query('SELECT * FROM tickets WHERE id = $1', [ticketId]);
  const ticket = result.rows[0];
  return {
    ...ticket,
    seatNumber: ticket.seat_number || 'GA',  // Default for old rows
  };
}
```

Deploy this code change. Now:
- New tickets get a proper `seat_number`
- Old tickets return `'GA'` as a default when read
- No downtime, no migration dependency

---

## 4. Build: Phase 3 -- Backfill in Batches (15 minutes)

This is the critical phase. You need to update 10 million rows without locking the table.

```typescript
// src/migrations/backfill-seat-number.ts

import { Pool } from 'pg';

const db = new Pool({ connectionString: process.env.DATABASE_URL });

interface BackfillConfig {
  batchSize: number;
  delayBetweenBatchesMs: number;
  dryRun: boolean;
}

async function backfillSeatNumber(config: BackfillConfig): Promise<void> {
  const { batchSize, delayBetweenBatchesMs, dryRun } = config;

  // Find the range of IDs to process
  const countResult = await db.query(
    'SELECT COUNT(*) as total FROM tickets WHERE seat_number IS NULL'
  );
  const total = parseInt(countResult.rows[0].total);
  console.log(`[backfill] ${total} rows to update`);

  if (total === 0) {
    console.log('[backfill] Nothing to backfill');
    return;
  }

  let updated = 0;
  let batchNumber = 0;

  while (true) {
    batchNumber++;

    // --- KEY TECHNIQUE: Update a limited batch using a subquery ---
    // This only locks the rows in the current batch, not the entire table.
    const sql = `
      UPDATE tickets
      SET seat_number = 'GA'
      WHERE id IN (
        SELECT id FROM tickets
        WHERE seat_number IS NULL
        LIMIT $1
        FOR UPDATE SKIP LOCKED
      )
    `;

    if (dryRun) {
      console.log(`[backfill] DRY RUN batch ${batchNumber}: would update ${batchSize} rows`);
      const peek = await db.query(
        'SELECT COUNT(*) as count FROM tickets WHERE seat_number IS NULL LIMIT $1',
        [batchSize]
      );
      if (parseInt(peek.rows[0].count) === 0) break;
    } else {
      const result = await db.query(sql, [batchSize]);
      const rowsAffected = result.rowCount || 0;
      updated += rowsAffected;

      const progress = ((updated / total) * 100).toFixed(1);
      console.log(
        `[backfill] Batch ${batchNumber}: updated ${rowsAffected} rows ` +
        `(${updated}/${total}, ${progress}%)`
      );

      // No more rows to update
      if (rowsAffected === 0) break;
    }

    // Pause between batches to let production queries breathe
    await new Promise(r => setTimeout(r, delayBetweenBatchesMs));
  }

  console.log(`[backfill] Complete: ${updated} rows updated in ${batchNumber} batches`);
}

// --- YOUR DECISION POINT ---
// What batch size and delay should you use?
//
// Aggressive: batchSize=10000, delay=100ms → finishes in ~17 minutes
//   Risk: may cause lock contention during peak hours
//
// Conservative: batchSize=1000, delay=500ms → finishes in ~83 minutes
//   Safe: minimal impact on production, but takes longer
//
// Adaptive: start conservative, increase if DB metrics look healthy
//
// Run this DURING LOW TRAFFIC HOURS even though it is safe.

const config: BackfillConfig = {
  batchSize: 5000,
  delayBetweenBatchesMs: 200,
  dryRun: process.argv.includes('--dry-run'),
};

backfillSeatNumber(config)
  .then(() => process.exit(0))
  .catch(err => {
    console.error('[backfill] FAILED:', err);
    process.exit(1);
  });
```

**Key details:**

- `FOR UPDATE SKIP LOCKED`: Locks only the batch rows and skips any that are currently locked by other transactions. This prevents deadlocks with concurrent application queries.
- Batch + delay: Each batch updates a small number of rows, then pauses to let other queries run.
- Resumable: If the backfill fails halfway, just run it again. It picks up where it left off (only updates rows where `seat_number IS NULL`).
- Dry run: Always test first.

Run it:

```bash
# Dry run first
npx ts-node src/migrations/backfill-seat-number.ts --dry-run

# Then for real
npx ts-node src/migrations/backfill-seat-number.ts
```

Monitor during the backfill:

```sql
-- Check progress
SELECT
  COUNT(*) FILTER (WHERE seat_number IS NOT NULL) AS done,
  COUNT(*) FILTER (WHERE seat_number IS NULL) AS remaining,
  COUNT(*) AS total
FROM tickets;
```

---

## 5. Build: Phase 4 -- Add Constraints (5 minutes)

Once every row has a value, add the NOT NULL constraint:

```sql
-- Migration: 002_seat_number_not_null.sql
-- Phase 4: CONTRACT

-- First, verify all rows have been backfilled
SELECT COUNT(*) FROM tickets WHERE seat_number IS NULL;
-- Must be 0

-- Add NOT NULL constraint
-- In Postgres 12+, adding NOT NULL with a CHECK constraint can be done without a full table scan
-- if you add the constraint as NOT VALID first, then validate separately:

-- Step 1: Add check constraint (instant, does not scan the table)
ALTER TABLE tickets ADD CONSTRAINT seat_number_not_null
  CHECK (seat_number IS NOT NULL) NOT VALID;

-- Step 2: Validate the constraint (scans the table but does not block writes)
ALTER TABLE tickets VALIDATE CONSTRAINT seat_number_not_null;

-- Step 3: Now you can safely add the NOT NULL modifier
-- (Postgres recognizes the validated check constraint and skips the scan)
ALTER TABLE tickets ALTER COLUMN seat_number SET NOT NULL;

-- Optional: drop the check constraint since NOT NULL is sufficient
ALTER TABLE tickets DROP CONSTRAINT seat_number_not_null;
```

Set the default for future rows:

```sql
-- In Postgres 11+, adding a default to an existing column is instant (metadata only)
ALTER TABLE tickets ALTER COLUMN seat_number SET DEFAULT 'GA';
```

---

## 6. Adding Indexes Concurrently (5 minutes)

TicketPulse needs to look up tickets by seat number. A normal `CREATE INDEX` locks the table for writes. `CREATE INDEX CONCURRENTLY` does not:

```sql
-- WRONG: locks the table
CREATE INDEX idx_tickets_seat ON tickets(seat_number);

-- RIGHT: does not lock the table (but takes longer and uses more resources)
CREATE INDEX CONCURRENTLY idx_tickets_seat ON tickets(seat_number);
```

**Caveats with CONCURRENTLY:**
- Cannot run inside a transaction block
- If it fails partway through, it leaves an INVALID index. Check with `\d tickets` and drop it if needed.
- Takes roughly 2-3x longer than a regular index creation
- Requires two table scans instead of one

```bash
# Run it and monitor
psql -d ticketpulse -c "CREATE INDEX CONCURRENTLY idx_tickets_seat ON tickets(seat_number);"

# Verify the index is valid (not INVALID)
psql -d ticketpulse -c "\d tickets"
```

---

## 7. The Hard Case: Renaming a Column (7 minutes)

What if instead of adding a column, you need to rename `ticket_type` to `tier_name`? You cannot rename a column while the old code is still reading `ticket_type`.

The four-step process:

```
Step 1: Add the new column (tier_name)
Step 2: Deploy code that writes to BOTH columns
Step 3: Backfill old rows (copy ticket_type → tier_name)
Step 4: Deploy code that reads from tier_name, drop old column
```

```sql
-- Step 1: Add new column
ALTER TABLE tickets ADD COLUMN tier_name VARCHAR(50);

-- (Deploy code that writes to both ticket_type AND tier_name)

-- Step 3: Backfill
UPDATE tickets SET tier_name = ticket_type WHERE tier_name IS NULL;
-- (Use the batched approach from Phase 3 for large tables)
```

```typescript
// Step 2: Application code writes to both columns
async function issueTicket(orderId: string, eventId: string, tierName: string): Promise<Ticket> {
  const result = await db.query(
    `INSERT INTO tickets (order_id, event_id, ticket_type, tier_name, status)
     VALUES ($1, $2, $3, $3, 'active')
     RETURNING *`,
    [orderId, eventId, tierName]  // Same value in both columns
  );
  return result.rows[0];
}

// Step 4: Reading code switches to new column (after backfill complete)
async function getTicket(ticketId: string): Promise<Ticket> {
  const result = await db.query('SELECT * FROM tickets WHERE id = $1', [ticketId]);
  return {
    ...result.rows[0],
    tierName: result.rows[0].tier_name,  // Read from new column
  };
}
```

```sql
-- Step 4: After all code reads from tier_name
ALTER TABLE tickets DROP COLUMN ticket_type;
```

This is more work than a simple `ALTER TABLE RENAME COLUMN`, but it has zero downtime.

---

## 8. Debug: What If the Backfill Fails Halfway? (5 minutes)

The backfill script updated 6 million of 10 million rows, then crashed (out of memory, network error, pod eviction). What do you do?

**Answer:** Run it again. The script only updates rows where `seat_number IS NULL`, so it resumes from where it stopped. The `FOR UPDATE SKIP LOCKED` clause prevents conflicts with concurrent transactions.

Verify the state:

```sql
SELECT
  COUNT(*) FILTER (WHERE seat_number IS NOT NULL) AS backfilled,
  COUNT(*) FILTER (WHERE seat_number IS NULL) AS remaining
FROM tickets;
-- backfilled: 6,000,000
-- remaining: 4,000,000
```

Run the script again. It processes only the remaining 4 million rows.

**What if the backfill is too slow?** Run multiple instances in parallel. Each one processes a different ID range:

```typescript
// Partition by ID range for parallel processing
const sql = `
  UPDATE tickets
  SET seat_number = 'GA'
  WHERE id IN (
    SELECT id FROM tickets
    WHERE seat_number IS NULL
    AND id >= $1 AND id < $2
    LIMIT $3
    FOR UPDATE SKIP LOCKED
  )
`;
```

Run three workers: one for IDs 1-3.3M, one for 3.3M-6.6M, one for 6.6M-10M.

---

> **What did you notice?** Zero-downtime migrations require the expand-and-contract pattern: add the new thing, migrate, remove the old thing. This is slower than a breaking change but avoids any gap in service. When is the extra effort justified?

## Exercises

### 🛠️ Build: Expand-Contract for Renaming `ticket_type` to `tier_name`

Implement the full four-step expand-and-contract migration to rename `ticket_type` to `tier_name` on a table with 10M rows, including the dual-write application code.

<details>
<summary>💡 Hint 1</summary>
Phase 1 (Expand): `ALTER TABLE tickets ADD COLUMN tier_name VARCHAR(50)` -- instant, nullable, no lock. Phase 2 (Deploy): update `issueTicket()` to write the same value to both `ticket_type` and `tier_name` in the INSERT statement. This ensures no new rows are missing `tier_name` from this point forward.
</details>

<details>
<summary>💡 Hint 2</summary>
Phase 3 (Backfill): reuse the batched backfill pattern with `FOR UPDATE SKIP LOCKED`: `UPDATE tickets SET tier_name = ticket_type WHERE tier_name IS NULL AND id IN (SELECT id FROM tickets WHERE tier_name IS NULL LIMIT 5000 FOR UPDATE SKIP LOCKED)`. Run with `--dry-run` first. The backfill is idempotent -- rerun if it crashes.
</details>

<details>
<summary>💡 Hint 3</summary>
Phase 4 (Contract): switch reads to `tier_name`, then drop `ticket_type`. Do NOT drop the old column in the same deploy as the code change -- wait for all pods to roll over to the new code first. If any old-code pod reads `ticket_type` after the column is dropped, it will crash. Wait at least one full rolling deployment cycle before running `ALTER TABLE tickets DROP COLUMN ticket_type`.
</details>

### 🐛 Debug: Backfill Halted at 60%

The backfill script updated 6M of 10M rows and then stopped making progress. The script reports `0 rows affected` on every batch, but `SELECT COUNT(*) FROM tickets WHERE seat_number IS NULL` still shows 4M remaining.

<details>
<summary>💡 Hint 1</summary>
`FOR UPDATE SKIP LOCKED` skips rows that are locked by other transactions. If another process is holding long-running transactions (e.g., a reporting query with `FOR SHARE` or a stuck migration), those rows are permanently skipped. Run `SELECT pid, state, query, age(clock_timestamp(), xact_start) FROM pg_stat_activity WHERE state != 'idle' ORDER BY xact_start` to find long-running transactions.
</details>

<details>
<summary>💡 Hint 2</summary>
Check if there is an open transaction holding locks: `SELECT locktype, relation::regclass, mode, granted, pid FROM pg_locks WHERE relation = 'tickets'::regclass AND NOT granted`. If rows show `RowExclusiveLock` not granted, another transaction is blocking. Terminate the blocking session with `SELECT pg_terminate_backend(<pid>)` after confirming it is safe.
</details>

<details>
<summary>💡 Hint 3</summary>
Alternative fix: remove `FOR UPDATE SKIP LOCKED` temporarily and replace with plain `WHERE seat_number IS NULL LIMIT 5000`. This will wait for locks instead of skipping, which is slower but guarantees progress. Once the blocking transaction is resolved, switch back to `SKIP LOCKED` for the remaining rows.
</details>

### 📐 Design: Type Change from INTEGER to UUID

TicketPulse needs to change `event_id` from `INTEGER` to `UUID` across the `tickets`, `orders`, and `pricing_tiers` tables. Design the expand-and-contract migration plan including foreign key handling.

<details>
<summary>💡 Hint 1</summary>
The expand-and-contract pattern applies to type changes too: add a new `event_id_uuid UUID` column, dual-write both columns, backfill old rows with a mapping (either generate UUIDs deterministically from the integer, or maintain a `event_id_mapping` lookup table). The foreign keys on `tickets.event_id` and `orders.event_id` must be duplicated to point at the new column.
</details>

<details>
<summary>💡 Hint 2</summary>
The tricky part is foreign key consistency. You cannot add a FK constraint on `event_id_uuid` until all rows have been backfilled. Use the same NOT VALID + VALIDATE trick: `ALTER TABLE tickets ADD CONSTRAINT fk_tickets_event_uuid FOREIGN KEY (event_id_uuid) REFERENCES events(id_uuid) NOT VALID` (instant), then `ALTER TABLE tickets VALIDATE CONSTRAINT fk_tickets_event_uuid` (scans but does not block writes).
</details>

<details>
<summary>💡 Hint 3</summary>
Create the migration plan as a document with explicit phases and rollback at each step: Phase 1 (add columns, no FK), Phase 2 (deploy dual-write code), Phase 3 (backfill with batched UPDATE), Phase 4 (add FK constraints NOT VALID + VALIDATE), Phase 5 (switch reads to UUID columns), Phase 6 (drop old integer columns). Each phase has a rollback: phases 1-4 can be rolled back by dropping the new columns; phases 5-6 require code rollback first.
</details>

---

## Checkpoint

Before continuing, verify:

- [ ] Column added without locking the table (nullable, no default)
- [ ] Application writes to the new column for all new records
- [ ] Backfill updates existing rows in batches (no full table lock)
- [ ] `FOR UPDATE SKIP LOCKED` prevents deadlocks
- [ ] NOT NULL constraint added after backfill, using NOT VALID + VALIDATE
- [ ] Index created with CONCURRENTLY (no write lock)
- [ ] Backfill is resumable if interrupted

```bash
git add -A && git commit -m "feat: zero-downtime migration for seat_number column with batch backfill"
```

---

## 9. Migration Rollback Drills

Every migration that goes forward should have a rollback path. This is not about being pessimistic — it is about being disciplined. If you cannot roll back a migration, you cannot safely deploy it.

### Drill 1: The Rollback Decision Tree

For each migration you run, answer these questions before starting. The answers determine your rollback strategy.

```
MIGRATION ROLLBACK PLANNING
═══════════════════════════

1. Is this migration reversible without data loss?
   - Adding a nullable column: YES (drop the column)
   - Dropping a column: NO (data is gone)
   - Adding NOT NULL to existing column: YES (revert to nullable)
   - Backfilling data: YES (column was nullable before)
   - Changing a column type: SOMETIMES (depends on data)

2. How long will the rollback take?
   - Metadata-only change (add nullable column): milliseconds
   - Re-backfilling removed data from backup: hours

3. What does the application do during rollback?
   - Is the application compatible with the pre-migration and post-migration schema?
   - Will the rollback break existing running application pods?

4. What is the rollback window?
   - If you discover a problem 2 hours after migration, can you still roll back?
   - If 1M new rows were written with the new schema, can you still roll back?
```

### Drill 2: Write the Rollback for the seat_number Migration

For every migration file, create a corresponding rollback file. Here is the pattern:

```
migrations/
  up/
    001_add_seat_number.sql       ← forward migration
    002_seat_number_not_null.sql  ← forward migration
  down/
    002_remove_seat_number_constraint.sql  ← rollback 002
    001_drop_seat_number.sql               ← rollback 001
```

```sql
-- down/002_remove_seat_number_constraint.sql
-- Rollback: remove NOT NULL constraint (restore nullable state)

ALTER TABLE tickets ALTER COLUMN seat_number DROP NOT NULL;
ALTER TABLE tickets ALTER COLUMN seat_number DROP DEFAULT;
-- Optionally: remove the index if it was added with NOT NULL
-- DROP INDEX IF EXISTS idx_tickets_seat;

-- Verify
SELECT column_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'tickets' AND column_name = 'seat_number';
-- Expected: is_nullable = YES, column_default = null
```

```sql
-- down/001_drop_seat_number.sql
-- Rollback: remove the seat_number column entirely
-- WARNING: This loses all seat_number data. Confirm the column was backfilled
-- from a reliable source (event data) that can be regenerated if needed.

-- Step 1: Verify you have a backup or the data is regeneratable
-- SELECT COUNT(*) FROM tickets WHERE seat_number IS NOT NULL; -- how much data?

-- Step 2: Drop the column
ALTER TABLE tickets DROP COLUMN IF EXISTS seat_number;

-- Verify
\d tickets -- seat_number column should be gone
```

**The rollback test**: After writing rollback scripts, run them in a staging environment:
1. Run the forward migration
2. Verify the application works
3. Run the rollback
4. Verify the application still works in the pre-migration state

If you cannot complete step 4, your rollback is broken.

### Drill 3: The "Migration Already Deployed" Rollback

The worst scenario: you migrated 6 hours ago, the application has been writing new data using the new schema, and now you need to roll back because of a production issue.

For the `seat_number` migration, here is what "roll back with 6 hours of live data" looks like:

```
State at T+6h:
- 50,000 new tickets written with seat_number values
- The application currently reads seat_number for display and QR code
- Rolling back (dropping seat_number) would break ticket display

Options:
1. DO NOT roll back the schema. Roll back only the application code.
   - Redeploy the previous version of the application
   - The previous application code reads seat_number as nullable
     (it was nullable in Phase 2) — it will fall back to 'GA'
   - The schema stays ahead of the application code
   - This is the expand-and-contract pattern working as intended

2. If the column itself is the problem (schema bug, wrong type):
   - Add a new corrected column (new expand phase)
   - Dual-write to both
   - The seat_number column stays (too many rows depend on it)
   - Contract later when the corrected column is stable
```

The lesson: **schema rollbacks after significant writes are almost always wrong**. Application code rollbacks are almost always right. The expand-and-contract pattern exists specifically to make this true.

### Drill 4: Rehearse the Worst Case

Run this simulation in staging before any production migration:

```bash
# 1. Start the application
docker compose up -d

# 2. Run the forward migration
psql -d ticketpulse -f migrations/up/001_add_seat_number.sql
psql -d ticketpulse -f migrations/up/002_seat_number_not_null.sql

# 3. Verify the app works
curl http://localhost:3000/api/events/evt_1/tickets
# Expect: 200 OK, seat_number field present

# 4. Simulate a production problem — reverse the migration
psql -d ticketpulse -f migrations/down/002_remove_seat_number_constraint.sql
psql -d ticketpulse -f migrations/down/001_drop_seat_number.sql

# 5. Verify the app STILL works (this is the key test)
curl http://localhost:3000/api/events/evt_1/tickets
# Expect: 200 OK, seat_number absent OR defaulted gracefully

# If step 5 fails: your application code is not compatible with both schema versions
# Fix it before going to production
```

---

## 10. The Expand-and-Contract Pattern: Four Scenarios

The expand-and-contract pattern covers four common migration shapes. Each has a different sequence and different risks.

### Scenario A: Adding a Column with Constraints

This is what you built in the main module. The sequence:

```
Phase 1 EXPAND:   ADD COLUMN seat_number VARCHAR(10)          ← nullable, instant
Phase 2 DEPLOY:   Deploy code that writes seat_number
Phase 3 BACKFILL: Fill existing rows in batches (days-weeks)
Phase 4 CONTRACT: ALTER COLUMN SET NOT NULL + ADD DEFAULT      ← after backfill done
```

**Risk point**: Phase 4. If a single row still has NULL, the NOT NULL constraint fails. Always run `SELECT COUNT(*) FROM tickets WHERE seat_number IS NULL` before Phase 4.

### Scenario B: Removing a Column

Removing a column safely requires going backwards through a deprecation cycle:

```
Phase 1 EXPAND:   Deploy code that stops READING the column   ← no schema change yet
Phase 2 EXPAND:   Deploy code that stops WRITING the column
Phase 3 VERIFY:   Wait for all pods to redeploy (rolling deploy)
Phase 4 CONTRACT: ALTER TABLE tickets DROP COLUMN old_column   ← now safe to drop
```

**The most common mistake**: Dropping the column in the same deploy as removing reads from the code. There is a window where old pods are still running (during rolling deployment) that will fail to read the dropped column.

### Scenario C: Renaming a Column

Renaming is the most complex case because it requires dual-write for an extended period:

```
Phase 1 EXPAND:   ADD COLUMN tier_name VARCHAR(50)             ← new column
Phase 2 DEPLOY:   Deploy code that READS from old, WRITES to both
Phase 3 BACKFILL: UPDATE tickets SET tier_name = ticket_type WHERE tier_name IS NULL
Phase 4 DEPLOY:   Deploy code that READS from new, WRITES to both
Phase 5 VERIFY:   No old-code pods running
Phase 6 CONTRACT: ALTER TABLE tickets DROP COLUMN ticket_type   ← drop old
```

Note that Phase 2 and Phase 4 are different deployments. Between them, new rows write to both columns. After Phase 4, reads come from the new column only.

### Scenario D: Changing a Column Type

For example, changing `event_id` from `INTEGER` to `UUID`:

```
Phase 1 EXPAND:   ADD COLUMN event_id_uuid UUID               ← new column
Phase 2 BACKFILL: UPDATE tickets SET event_id_uuid = uuid_generate_v4()
                  WHERE event_id_uuid IS NULL -- or map from integer IDs
Phase 3 DEPLOY:   Write to both event_id (int) and event_id_uuid (uuid)
Phase 4 DEPLOY:   Read from event_id_uuid, still write to both (safety net)
Phase 5 CONTRACT: Drop old event_id column
```

**The key challenge in type changes**: The new column must be populated with values derived from the old column. If the mapping is complex (integer ID → UUID), you need a lookup table or a UUID-per-integer mapping table to ensure foreign key consistency.

---

## Reflect

GitHub built the `gh-ost` tool because traditional `ALTER TABLE` locked their tables for hours. Facebook built `OnlineSchemaChange` for the same reason. These tools exist because zero-downtime migrations are a universal problem at scale.

The expand-and-contract pattern works for any schema change:
- **Adding a column**: expand (add nullable), backfill, contract (add constraint)
- **Removing a column**: expand (stop reading), contract (drop column)
- **Renaming a column**: expand (add new), dual-write, backfill, contract (drop old)
- **Changing a type**: expand (add new column with new type), dual-write, backfill with conversion, contract

The key insight: **every migration is a multi-step process with application deployments between steps**. This is more work than a single ALTER TABLE, but it is the price of keeping the system available during changes.

---

---

## Cross-References

- **Chapter 24** (Database Internals): PostgreSQL's MVCC model is why some DDL operations lock and others do not. Understanding how Postgres handles concurrent reads and writes during `ALTER TABLE` requires the internals covered there.
- **Chapter 7** (Deployment Strategies): Zero-downtime schema migrations require rolling deployments to work correctly. A blue-green deploy and a staged migration sequence must be coordinated. Chapter 7 covers the deployment mechanics.
- **L2-M43** (Kubernetes Fundamentals): Kubernetes rolling deployments create the "window of mixed versions" that drives the expand-and-contract pattern's requirement to support both schemas simultaneously.

---

## Key Terms

| Term | Definition |
|------|-----------|
| **Schema migration** | A versioned change to the database schema (tables, columns, indexes) applied in a controlled sequence. |
| **Expand-and-contract** | A migration strategy that first adds new structures (expand), migrates data, then removes old structures (contract). |
| **Backfill** | The process of populating a new column or table with data derived from existing records. |
| **Zero-downtime** | A deployment or migration approach that keeps the application available to users throughout the change. |
| **DDL** | Data Definition Language; SQL statements (CREATE, ALTER, DROP) that define or modify database schema objects. |
| **Dual-write** | A migration phase where application code writes to both the old and new columns simultaneously to maintain consistency. |
| **Rollback window** | The time period after a migration during which rolling back is safe; shrinks as new data accumulates in the new schema. |
| **Schema compatibility** | The property that application code can operate correctly against both the pre-migration and post-migration schema. |

---

## What's Next

In **Webhooks** (L2-M55), you'll build a webhook system that lets external services subscribe to TicketPulse events with reliable delivery.

---

## Further Reading

- GitHub Engineering Blog, "gh-ost: GitHub's online schema migration tool for MySQL"
- Postgres documentation on `ALTER TABLE` and which operations require table rewrites
- "Designing Data-Intensive Applications" by Martin Kleppmann, Chapter 4 -- encoding, evolution, and schema changes
- Stripe's approach to zero-downtime migrations -- practical patterns for a system that processes billions of dollars
