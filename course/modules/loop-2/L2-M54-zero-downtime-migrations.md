# L2-M54: Zero-Downtime Migrations

> **Loop 2 (Applied)** | Section 2D: Advanced Patterns | Duration: 60 min | Tier: Core
>
> **Prerequisites:** L2-M39 (Kubernetes Basics), familiarity with Postgres
>
> **What you'll build:** You will perform a zero-downtime schema migration on TicketPulse's tickets table (10M rows) using the expand-and-contract pattern -- adding a column, backfilling in batches, adding constraints, creating concurrent indexes, and handling the column rename case.

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

## Reflect

GitHub built the `gh-ost` tool because traditional `ALTER TABLE` locked their tables for hours. Facebook built `OnlineSchemaChange` for the same reason. These tools exist because zero-downtime migrations are a universal problem at scale.

The expand-and-contract pattern works for any schema change:
- **Adding a column**: expand (add nullable), backfill, contract (add constraint)
- **Removing a column**: expand (stop reading), contract (drop column)
- **Renaming a column**: expand (add new), dual-write, backfill, contract (drop old)
- **Changing a type**: expand (add new column with new type), dual-write, backfill with conversion, contract

The key insight: **every migration is a multi-step process with application deployments between steps**. This is more work than a single ALTER TABLE, but it is the price of keeping the system available during changes.

---

## Further Reading

- GitHub Engineering Blog, "gh-ost: GitHub's online schema migration tool for MySQL"
- Postgres documentation on `ALTER TABLE` and which operations require table rewrites
- "Designing Data-Intensive Applications" by Martin Kleppmann, Chapter 4 -- encoding, evolution, and schema changes
- Stripe's approach to zero-downtime migrations -- practical patterns for a system that processes billions of dollars
