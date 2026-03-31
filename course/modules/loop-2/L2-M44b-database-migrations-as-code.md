# L2-M44b: Database Migrations as Code

> **Loop 2 (Practice)** | Section 2C: Infrastructure & Operations | ⏱️ 75 min | 🟢 Core | Prerequisites: L1-M06, L2-M44
>
> **Source:** Chapter 35 of the 100x Engineer Guide

## What You'll Learn

- Why database schema changes must be version-controlled migration files, not ad-hoc SQL
- Setting up golang-migrate from scratch for TicketPulse
- Writing complete up/down migration pairs for TicketPulse's core tables (users, events, tickets)
- The migration lifecycle: up, down, version, force, and the schema_migrations table
- Diagnosing and recovering from dirty migration state with exact commands
- Zero-downtime migration patterns: expand-contract worked example (rename venue to location)
- Separating schema migrations from data migrations with batched backfills
- Running and validating migrations in CI with a complete Makefile
- What happens when two developers create the same migration number on different branches

## Why This Matters

TicketPulse's database schema has been evolving since L1-M05. You have created tables, added columns, and built indexes. But how did you make those changes? If you ran `CREATE TABLE` directly in psql, that change exists only in your local database. Your teammate's database is different. CI spins up a fresh database with no tables at all.

Migrations solve this: every schema change is a numbered file in Git. Running `migrate up` on any database -- local, CI, staging, production -- produces the same schema. The migration history IS the documentation. Rolling back a bad deploy means running `migrate down`, not guessing what SQL to undo.

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases -- Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

## Prereq Check

```bash
# Ensure TicketPulse's PostgreSQL is running
docker compose up -d postgres
psql postgresql://localhost:5432/ticketpulse -c "SELECT 1"

# Install golang-migrate
# macOS
brew install golang-migrate

# Linux (Debian/Ubuntu)
curl -L https://github.com/golang-migrate/migrate/releases/download/v4.17.0/migrate.linux-amd64.tar.gz | tar xvz
sudo mv migrate /usr/local/bin/migrate

# Verify
migrate --version
# Should show: 4.17.0 or similar
```

---

## 1. Why Migrations, Not Ad-Hoc SQL

Without migrations:
- Someone runs `ALTER TABLE` in production during a Zoom call
- Staging and production schemas silently drift
- New team members spend a day reverse-engineering the current schema
- Rolling back a deployment does not roll back the schema -- data corruption ensues

With migrations:
- Every schema change is a versioned file in Git, reviewed in a PR
- `migrate up` produces the same schema everywhere: dev, CI, staging, production
- Rollback is `migrate down` (if you wrote the down migration)
- The migration history IS the schema documentation

### How golang-migrate Works

golang-migrate maintains a `schema_migrations` table with two columns: `version` (integer) and `dirty` (boolean). It reads migration files from a directory, ordered by numeric prefix, and applies pending ones in order. Each migration has an up file and a down file:

```
000001_create_users_table.up.sql       # Applied by "migrate up"
000001_create_users_table.down.sql     # Applied by "migrate down"
```

---

## 2. Build: TicketPulse's Core Schema

Create the migrations directory:

```bash
mkdir -p db/migrations
cd db/migrations
```

We will define a `DATABASE_URL` variable to avoid repeating the connection string:

```bash
export DATABASE_URL="postgresql://localhost:5432/ticketpulse?sslmode=disable"
```

### Migration 1: Users Table

```bash
migrate create -ext sql -dir db/migrations -seq create_users_table
```

This creates two empty files. Fill them in:

```sql
-- db/migrations/000001_create_users_table.up.sql
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(255) NOT NULL,
    role          VARCHAR(50)  NOT NULL DEFAULT 'customer',
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
```

```sql
-- db/migrations/000001_create_users_table.down.sql
DROP TABLE IF EXISTS users;
```

### Migration 2: Events Table

```bash
migrate create -ext sql -dir db/migrations -seq create_events_table
```

```sql
-- db/migrations/000002_create_events_table.up.sql
CREATE TABLE IF NOT EXISTS events (
    id           BIGSERIAL    PRIMARY KEY,
    name         VARCHAR(255) NOT NULL,
    description  TEXT,
    venue        VARCHAR(255) NOT NULL,
    event_date   TIMESTAMP    NOT NULL,
    capacity     INTEGER      NOT NULL CHECK (capacity > 0),
    price_cents  INTEGER      NOT NULL CHECK (price_cents >= 0),
    created_by   BIGINT       REFERENCES users(id),
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_date ON events(event_date);
CREATE INDEX idx_events_created_by ON events(created_by);
```

```sql
-- db/migrations/000002_create_events_table.down.sql
DROP TABLE IF EXISTS events;
```

### Migration 3: Tickets Table

```bash
migrate create -ext sql -dir db/migrations -seq create_tickets_table
```

```sql
-- db/migrations/000003_create_tickets_table.up.sql
CREATE TABLE IF NOT EXISTS tickets (
    id          BIGSERIAL    PRIMARY KEY,
    event_id    BIGINT       NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id     BIGINT       REFERENCES users(id),
    seat_number VARCHAR(20),
    price_cents INTEGER      NOT NULL CHECK (price_cents >= 0),
    reserved_at TIMESTAMP,
    payment_id  VARCHAR(255),
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tickets_event_id ON tickets(event_id);
CREATE INDEX idx_tickets_user_id ON tickets(user_id);
CREATE INDEX idx_tickets_payment_id ON tickets(payment_id) WHERE payment_id IS NOT NULL;
```

```sql
-- db/migrations/000003_create_tickets_table.down.sql
DROP TABLE IF EXISTS tickets;
```

### Migration 4: Add Email Index to Tickets

```bash
migrate create -ext sql -dir db/migrations -seq add_email_to_tickets
```

```sql
-- db/migrations/000004_add_email_to_tickets.up.sql
ALTER TABLE tickets ADD COLUMN buyer_email VARCHAR(255);

CREATE INDEX idx_tickets_buyer_email ON tickets(buyer_email)
    WHERE buyer_email IS NOT NULL;
```

```sql
-- db/migrations/000004_add_email_to_tickets.down.sql
DROP INDEX IF EXISTS idx_tickets_buyer_email;
ALTER TABLE tickets DROP COLUMN IF EXISTS buyer_email;
```

### Apply All Migrations

```bash
migrate -path db/migrations -database "${DATABASE_URL}" up
```

Expected output:

```
1/u create_users_table (12.345ms)
2/u create_events_table (8.901ms)
3/u create_tickets_table (10.234ms)
4/u add_email_to_tickets (6.789ms)
```

Verify the result:

```bash
# List all tables
psql "${DATABASE_URL}" -c "\dt"

#              List of relations
#  Schema |       Name        | Type  |  Owner
# --------+-------------------+-------+----------
#  public | events            | table | postgres
#  public | schema_migrations | table | postgres
#  public | tickets           | table | postgres
#  public | users             | table | postgres

# List all indexes
psql "${DATABASE_URL}" -c "\di"

# Check migration version
psql "${DATABASE_URL}" -c "SELECT * FROM schema_migrations;"

#  version | dirty
# ---------+-------
#        4 | f
```

The `schema_migrations` table shows version 4, dirty = false. This means all four migrations have been applied successfully.

### Rollback

```bash
migrate -path db/migrations -database "${DATABASE_URL}" down 1     # Undo last migration
migrate -path db/migrations -database "${DATABASE_URL}" goto 2     # Roll back to version 2
migrate -path db/migrations -database "${DATABASE_URL}" down -all  # Roll back everything
migrate -path db/migrations -database "${DATABASE_URL}" up         # Re-apply all
```

`down 1` means "run one down migration." `goto 2` means "move to version 2, running as many down migrations as needed."

---

## 3. Debug: The Dirty State Problem

This is the scenario every developer hits exactly once -- and panics. Let us cause it deliberately.

### Create a Broken Migration

```bash
migrate create -ext sql -dir db/migrations -seq bad_migration
```

```sql
-- db/migrations/000005_bad_migration.up.sql
ALTER TABLE events ADD COLUMN foo INTEGR;  -- typo: INTEGR instead of INTEGER
```

```sql
-- db/migrations/000005_bad_migration.down.sql
ALTER TABLE events DROP COLUMN IF EXISTS foo;
```

### Run It and Watch It Fail

```bash
migrate -path db/migrations -database "${DATABASE_URL}" up
```

Output:

```
5/u bad_migration (0.000ms)
error: migration failed: type "integr" does not exist (column "foo"
of relation "events") in line 1: ALTER TABLE events ADD COLUMN foo
INTEGR; (details: pq: type "integr" does not exist)
```

Now check the state:

```bash
migrate -path db/migrations -database "${DATABASE_URL}" version
```

Output:

```
5 (dirty)
```

This is the critical moment. The database says "I am on version 5, and it is dirty." What does dirty mean? The migration started but failed partway through. golang-migrate does not know whether any changes were partially applied. It refuses to run any further migrations until you resolve the situation.

### Why Can't You Just Run `up` Again?

```bash
migrate -path db/migrations -database "${DATABASE_URL}" up
```

Output:

```
error: Dirty database version 5. Fix and force version.
```

The tool refuses. It does not know if the broken migration left partial changes (maybe it created a column before the error, maybe it did not). You need to investigate and fix manually.

### Recovery: Step by Step

**Step 1: Check what actually happened in the database.**

```bash
psql "${DATABASE_URL}" -c "\d events"
```

Look at the columns. Does `foo` exist? In this case it does not -- the entire statement failed because `INTEGR` is not a valid type. PostgreSQL DDL is transactional, so the failed `ALTER TABLE` left no partial changes.

**Step 2: Force the version back to the last successful migration.**

```bash
migrate -path db/migrations -database "${DATABASE_URL}" force 4
```

This sets `schema_migrations` to version 4, dirty = false. It does NOT run any SQL. It only updates the tracking table. You are telling the tool: "Trust me, the database is actually at version 4."

**Step 3: Fix the migration file.**

```sql
-- db/migrations/000005_bad_migration.up.sql (fixed)
ALTER TABLE events ADD COLUMN foo INTEGER;
```

**Step 4: Re-run.**

```bash
migrate -path db/migrations -database "${DATABASE_URL}" up
```

Output:

```
5/u bad_migration (5.678ms)
```

**Step 5: Clean up (remove the test migration).**

```bash
migrate -path db/migrations -database "${DATABASE_URL}" down 1
rm db/migrations/000005_bad_migration.*.sql
```

> **The rule:** When you see "dirty database," do not panic. Check what actually changed in the database, force the version to the last clean state, fix the file, and re-run. Never use `force` to skip a version -- that leaves your schema out of sync with the migration history.

---

## 4. Zero-Downtime: Expand-Contract Migration

TicketPulse needs to rename the `venue` column to `location` in the events table. The product team wants a more general term because events can happen at virtual locations too.

You CANNOT do this:

```sql
ALTER TABLE events RENAME COLUMN venue TO location;  -- BREAKS running app!
```

Why? During deployment, old application instances are still reading `SELECT venue FROM events`. The moment you rename the column, those queries fail with `column "venue" does not exist`. You get 500 errors during the rolling deploy.

The expand-contract pattern solves this in three phases.

### Phase 1: Expand (Migration 5)

Add the new column alongside the old one. Copy existing data. Make both columns available.

```bash
migrate create -ext sql -dir db/migrations -seq add_location_column
```

```sql
-- db/migrations/000005_add_location_column.up.sql
-- Phase 1: EXPAND - add new column, copy data, add trigger for dual-write
ALTER TABLE events ADD COLUMN location VARCHAR(255);

-- Backfill existing data
UPDATE events SET location = venue WHERE location IS NULL;

-- Create a trigger so any writes to 'venue' also update 'location'
-- This handles old app instances that still write to 'venue'
CREATE OR REPLACE FUNCTION sync_venue_to_location()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.venue IS DISTINCT FROM OLD.venue THEN
        NEW.location := NEW.venue;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_venue_to_location
    BEFORE UPDATE ON events
    FOR EACH ROW
    EXECUTE FUNCTION sync_venue_to_location();
```

```sql
-- db/migrations/000005_add_location_column.down.sql
DROP TRIGGER IF EXISTS trg_sync_venue_to_location ON events;
DROP FUNCTION IF EXISTS sync_venue_to_location();
ALTER TABLE events DROP COLUMN IF EXISTS location;
```

Apply it:

```bash
migrate -path db/migrations -database "${DATABASE_URL}" up
```

At this point, the events table has BOTH `venue` and `location` columns with identical data. Old app code reads `venue` and works. New app code can read `location` and works.

### Phase 2: Update Application Code (No Migration)

Deploy new application code that reads from `location` and writes to BOTH `venue` and `location`. Wait until all old application instances have been replaced. Use your observability tooling or `pg_stat_statements` to confirm no queries still reference only `venue`.

### Phase 3: Contract (Migration 6)

Once all application instances read from `location`, remove the old column and the sync trigger.

```bash
migrate create -ext sql -dir db/migrations -seq drop_venue_column
```

```sql
-- db/migrations/000006_drop_venue_column.up.sql
-- Phase 3: CONTRACT - remove old column and sync infrastructure
DROP TRIGGER IF EXISTS trg_sync_venue_to_location ON events;
DROP FUNCTION IF EXISTS sync_venue_to_location();

-- Make location NOT NULL now that it is the canonical column
ALTER TABLE events ALTER COLUMN location SET NOT NULL;

-- Drop the old column
ALTER TABLE events DROP COLUMN venue;
```

```sql
-- db/migrations/000006_drop_venue_column.down.sql
-- Reverse: re-add venue and copy data back from location
ALTER TABLE events ADD COLUMN venue VARCHAR(255);
UPDATE events SET venue = location;
ALTER TABLE events ALTER COLUMN location DROP NOT NULL;
-- Note: re-creating the sync trigger is omitted here because this
-- down migration restores the Phase 1 state. Re-apply migration 5's
-- down and then up if you need the trigger back.
```

> **Key insight:** Migrations 5 and 6 are NOT deployed together. Migration 5 is deployed with the app update. Migration 6 is deployed days or weeks later, after you have confirmed no code reads `venue`. This is the "contract" -- you contract the schema by removing the temporary redundancy.

---

## 5. Data Migrations: Backfill Ticket Status

Schema migrations change structure (DDL: `CREATE`, `ALTER`, `DROP`). Data migrations change content (DML: `INSERT`, `UPDATE`, `DELETE`). Keep them separate -- always.

### The Scenario

TicketPulse needs a `status` column on tickets with three values: `available`, `reserved`, `sold`. Existing tickets have no status. You need to backfill based on business logic:

- Tickets with a `payment_id` are `sold`
- Tickets with a `reserved_at` timestamp (but no payment) are `reserved`
- All others are `available`

### Why Three Separate Migrations?

```
000007_add_status_column.up.sql         -- Schema: ADD COLUMN
000008_backfill_ticket_status.up.sql    -- Data: UPDATE based on logic
000009_make_status_not_null.up.sql      -- Schema: SET NOT NULL + CHECK
```

If you combine all three into one migration and the backfill fails at row 50,000 (timeout, connection drop), the schema change is already committed. You cannot retry just the data part. Separating them means: if the backfill fails, run `force 7`, fix the issue, and retry migration 8 alone.

### Migration 7: Add the Column

```bash
migrate create -ext sql -dir db/migrations -seq add_status_column
```

```sql
-- db/migrations/000007_add_status_column.up.sql
ALTER TABLE tickets ADD COLUMN status VARCHAR(20) DEFAULT 'available';
```

```sql
-- db/migrations/000007_add_status_column.down.sql
ALTER TABLE tickets DROP COLUMN IF EXISTS status;
```

### Migration 8: Backfill with Batching

Large backfills on production tables must be batched. Running `UPDATE tickets SET status = ...` on a million-row table locks the table for the entire transaction and can cause downtime.

```bash
migrate create -ext sql -dir db/migrations -seq backfill_ticket_status
```

```sql
-- db/migrations/000008_backfill_ticket_status.up.sql

-- Backfill in batches of 10,000 to avoid long locks on large tables.
-- Each DO block processes one status value.

-- 1. Sold tickets (have a payment_id)
DO $$
DECLARE
    batch_size INTEGER := 10000;  rows_updated INTEGER;
BEGIN
    LOOP
        UPDATE tickets SET status = 'sold', updated_at = CURRENT_TIMESTAMP
        WHERE id IN (
            SELECT id FROM tickets
            WHERE  payment_id IS NOT NULL AND (status IS NULL OR status = 'available')
            LIMIT  batch_size FOR UPDATE SKIP LOCKED
        );
        GET DIAGNOSTICS rows_updated = ROW_COUNT;
        EXIT WHEN rows_updated = 0;
        PERFORM pg_sleep(0.1);  -- yield to other transactions
    END LOOP;
END $$;

-- 2. Reserved tickets (have reserved_at but no payment_id)
DO $$
DECLARE
    batch_size INTEGER := 10000;  rows_updated INTEGER;
BEGIN
    LOOP
        UPDATE tickets SET status = 'reserved', updated_at = CURRENT_TIMESTAMP
        WHERE id IN (
            SELECT id FROM tickets
            WHERE  reserved_at IS NOT NULL AND payment_id IS NULL
            AND    (status IS NULL OR status = 'available')
            LIMIT  batch_size FOR UPDATE SKIP LOCKED
        );
        GET DIAGNOSTICS rows_updated = ROW_COUNT;
        EXIT WHEN rows_updated = 0;
        PERFORM pg_sleep(0.1);
    END LOOP;
END $$;

-- 3. Everything else is 'available' (the default), but be explicit
UPDATE tickets SET status = 'available', updated_at = CURRENT_TIMESTAMP
WHERE status IS NULL;
```

```sql
-- db/migrations/000008_backfill_ticket_status.down.sql
-- Data backfill rollback: set everything back to NULL
-- (the column itself is removed by rolling back migration 7)
UPDATE tickets SET status = NULL;
```

> **Why `FOR UPDATE SKIP LOCKED`?** It grabs a batch of rows and locks only those rows, skipping any that are already locked by concurrent transactions. This prevents the backfill from blocking normal ticket purchases.

### Migration 9: Add the Constraint

```bash
migrate create -ext sql -dir db/migrations -seq make_status_not_null
```

```sql
-- db/migrations/000009_make_status_not_null.up.sql
-- Verify no NULLs remain before adding constraint
DO $$
DECLARE
    null_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO null_count FROM tickets WHERE status IS NULL;
    IF null_count > 0 THEN
        RAISE EXCEPTION 'Cannot add NOT NULL: % tickets still have NULL status', null_count;
    END IF;
END $$;

ALTER TABLE tickets ALTER COLUMN status SET NOT NULL;

ALTER TABLE tickets ADD CONSTRAINT chk_ticket_status
    CHECK (status IN ('available', 'reserved', 'sold'));

CREATE INDEX idx_tickets_status ON tickets(status);
```

```sql
-- db/migrations/000009_make_status_not_null.down.sql
DROP INDEX IF EXISTS idx_tickets_status;
ALTER TABLE tickets DROP CONSTRAINT IF EXISTS chk_ticket_status;
ALTER TABLE tickets ALTER COLUMN status DROP NOT NULL;
```

Apply the sequence:

```bash
migrate -path db/migrations -database "${DATABASE_URL}" up
```

```
7/u add_status_column (4.567ms)
8/u backfill_ticket_status (234.567ms)
9/u make_status_not_null (12.345ms)
```

---

## 6. The Collision Problem: Same Migration Number

This happens on every team eventually.

### The Scenario

Alice and Bob both branch from main at migration version 9. They each create a new migration:

```
Alice's branch:
  db/migrations/000010_add_organizer_table.up.sql

Bob's branch:
  db/migrations/000010_add_promo_codes_table.up.sql
```

Alice merges first. Bob's PR now has a conflict -- not a Git merge conflict (different files, different names), but a migration number collision. When CI runs `migrate up` on Bob's branch, it skips 000010 (already applied from Alice's migration) and has no record of Bob's migration.

### The Fix

Bob must renumber his migration before merging:

```bash
# Bob renames his files
mv db/migrations/000010_add_promo_codes_table.up.sql \
   db/migrations/000011_add_promo_codes_table.up.sql
mv db/migrations/000010_add_promo_codes_table.down.sql \
   db/migrations/000011_add_promo_codes_table.down.sql
```

### Prevention: Timestamp-Based Naming

Some teams switch to timestamp prefixes to avoid collisions entirely:

```bash
# Use -seq for sequential (000001, 000002, ...)
migrate create -ext sql -dir db/migrations -seq my_migration

# Use timestamps instead (20260331143022, ...)
migrate create -ext sql -dir db/migrations -digits 14 my_migration
```

With timestamps, Alice gets `20260331100000_add_organizer_table` and Bob gets `20260331103000_add_promo_codes_table`. No collision. golang-migrate applies them in numeric order regardless.

The tradeoff: sequential numbers are easier to read and discuss ("migration 10 broke staging"). Timestamps avoid collisions but are harder to reference in conversation. Most teams start with sequential and switch to timestamps when collisions become frequent.

A CI guard for this is included in the Makefile in section 7 (`db-check-duplicates` target).

---

## 7. CI Validation: Complete Makefile

This Makefile starts a disposable PostgreSQL container, runs all migrations forward, verifies the schema, runs all migrations backward, and cleans up. If any step fails, the CI job fails.

```makefile
# Makefile — migration targets

MIGRATION_DIR := db/migrations
TEST_DB_NAME  := migration-test-db
TEST_DB_PORT  := 5433
TEST_DB_PASS  := test-password
TEST_DB_URL   := postgresql://postgres:$(TEST_DB_PASS)@localhost:$(TEST_DB_PORT)/postgres?sslmode=disable

.PHONY: db-validate db-up db-down db-version db-create db-check-duplicates

# ── CI: full up + down validation on a disposable database ──────────────

db-validate: db-check-duplicates
	@docker rm -f $(TEST_DB_NAME) 2>/dev/null || true
	@docker run -d --name $(TEST_DB_NAME) \
		-e POSTGRES_PASSWORD=$(TEST_DB_PASS) -p $(TEST_DB_PORT):5432 postgres:16 > /dev/null
	@until docker exec $(TEST_DB_NAME) pg_isready -U postgres > /dev/null 2>&1; do sleep 1; done
	@echo "--- UP migrations ---"
	migrate -path $(MIGRATION_DIR) -database "$(TEST_DB_URL)" up
	@echo "--- Verify tables exist ---"
	@docker exec $(TEST_DB_NAME) psql -U postgres -c "\dt" | grep -qE "events|tickets|users" \
		|| (echo "FAIL: expected tables missing" && exit 1)
	@echo "--- DOWN migrations ---"
	migrate -path $(MIGRATION_DIR) -database "$(TEST_DB_URL)" down -all
	@echo "--- Verify clean state ---"
	@COUNT=$$(docker exec $(TEST_DB_NAME) psql -U postgres -tAc \
		"SELECT COUNT(*) FROM information_schema.tables \
		 WHERE table_schema='public' AND table_name!='schema_migrations'"); \
	[ "$$COUNT" = "0" ] || (echo "FAIL: $$COUNT tables remain" && exit 1)
	@docker rm -f $(TEST_DB_NAME) > /dev/null
	@echo "All migrations validated."

# ── Duplicate migration number guard ────────────────────────────────────

db-check-duplicates:
	@dupes=$$(ls $(MIGRATION_DIR)/*.sql 2>/dev/null | sed 's|.*/||' \
		| cut -d'_' -f1 | sort | uniq -d); \
	[ -z "$$dupes" ] || (echo "FAIL: duplicate migration numbers: $$dupes" && exit 1)

# ── Local helpers ───────────────────────────────────────────────────────

db-up:      ; migrate -path $(MIGRATION_DIR) -database "$(DATABASE_URL)" up
db-down:    ; migrate -path $(MIGRATION_DIR) -database "$(DATABASE_URL)" down 1
db-version: ; migrate -path $(MIGRATION_DIR) -database "$(DATABASE_URL)" version
db-create:  ; @read -p "Name: " n; migrate create -ext sql -dir $(MIGRATION_DIR) -seq $$n
```

In GitHub Actions, trigger `make db-validate` on PRs that touch `db/migrations/**`. The Makefile handles the full lifecycle (start container, migrate up, verify, migrate down, verify, clean up), so your workflow step is a single `run: make db-validate`.

---

## 8. Tool Comparison

Not every project uses golang-migrate. Here is how the major tools compare:

| Tool | Language | Approach | Rollback Support | SQL or ORM | Best For |
|---|---|---|---|---|---|
| **golang-migrate** | Go (binary) | Versioned, raw SQL | Manual (write down files) | Raw SQL | Go projects, polyglot teams, simplicity |
| **Flyway** | Java (runs anywhere) | Versioned SQL | Manual (V + U files) | Raw SQL | JVM projects, enterprise compliance |
| **Alembic** | Python | Versioned + autogenerate | Automatic (down revision) | SQLAlchemy models or raw SQL | Python/SQLAlchemy projects |
| **Prisma Migrate** | TypeScript | Declarative schema, generated SQL | Not built-in (manual workaround) | Prisma schema DSL | TypeScript/Node.js projects |
| **Atlas** | Go | Declarative + versioned hybrid | Planned migrations | HCL or SQL schema | Schema-as-code, drift detection |
| **Django Migrations** | Python | Model-first, autogenerate | Automatic | Django ORM | Django projects (tightly coupled) |
| **Drizzle Kit** | TypeScript | Declarative schema, generated SQL | Manual | TypeScript schema DSL | TypeScript, lightweight |
| **Liquibase** | Java | Versioned (XML/YAML/SQL) | Automatic rollback | Multiple formats | Complex rollback requirements |

### When to Choose What

**Choose golang-migrate or Flyway** when your team writes raw SQL and wants full control over every statement. You know exactly what runs against the database. No magic.

**Choose Alembic or Django** when your project already uses SQLAlchemy or Django. Autogenerate detects model changes and writes migration files for you. Review the generated SQL before applying.

**Choose Prisma Migrate or Drizzle Kit** when your project is TypeScript and you want a single schema definition that generates both migrations and type-safe client code.

**Choose Atlas** when you want declarative schema management (define the desired state, let the tool compute the diff) with the safety of reviewing generated SQL before it runs. Atlas also detects schema drift in production.

---

## 9. Reflect

> **"Should you ever edit an already-applied migration?"**
>
> No. Once a migration has been applied to any shared database (CI, staging, production), treat it as immutable. If migration 5 has a bug, do not edit 000005. Create migration 10 to fix the problem. Editing applied migrations causes checksum mismatches (Flyway will refuse to run), and your local database will differ from production because you ran the edited version but production ran the original. The one exception: if the migration was ONLY applied to your local database and has not been pushed to any branch, you can edit it -- it is effectively a draft.

> **"When would you choose a declarative tool (Atlas, Prisma Migrate) over a versioned tool (Flyway, golang-migrate)?"**
>
> Declarative tools shine when your schema is complex and changes frequently. Instead of writing `ALTER TABLE` by hand, you edit the desired schema and the tool generates the migration. This eliminates a class of bugs (forgetting to add an index, getting a constraint wrong). The tradeoff: you lose direct control over the exact SQL that runs, and complex data migrations still require manual SQL files. Most teams that start declarative eventually add escape hatches for data migrations.

> **"What happens if a migration takes 30 minutes on production but 2 seconds on staging?"**
>
> Table size. Staging might have 1,000 rows while production has 10 million. `ALTER TABLE ... ADD COLUMN` on a large table can lock it for the entire operation (depending on the database and the operation). Solutions: test migrations against a production-sized copy of the data (anonymized), use online DDL tools like `pg_repack` or `gh-ost`, and always separate schema from data migrations so the long-running backfill can be batched.

> **"How does TicketPulse's migration workflow compare to Django's auto-generated migrations?"**
>
> Django inspects your Python models, detects what changed, and auto-generates a migration file. golang-migrate does nothing automatically -- you write every line of SQL. Django's approach is faster for development but hides the SQL. golang-migrate's approach is more work but gives you full visibility and control. In production, both produce the same result: numbered files applied in order. The real question is whether your team is more comfortable reviewing Python migration operations or raw SQL.

---

## 10. Checkpoint

After this module, your TicketPulse migration setup should have:

- [ ] golang-migrate installed and working
- [ ] `db/migrations/` directory with at least 9 migration pairs (up + down)
- [ ] Core tables created: users, events, tickets
- [ ] Successfully applied and rolled back all migrations
- [ ] Experienced and recovered from a dirty migration state
- [ ] Expand-contract migration for venue-to-location rename (migrations 5-6)
- [ ] Data backfill migration with batching for ticket status (migrations 7-9)
- [ ] `make db-validate` runs all migrations up and down on a clean database
- [ ] CI workflow that validates migrations on every PR touching `db/migrations/`
- [ ] Duplicate migration number detection script
- [ ] Understanding of when to use sequential vs timestamp-based naming

**Next up:** L2-M45 where we add Prometheus and Grafana to monitor everything we have deployed.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Migration** | A versioned file that describes a single, atomic schema or data change to a database. Applied in order. |
| **Up migration** | The forward direction: applies the change (CREATE TABLE, ALTER COLUMN, etc.). |
| **Down migration** | The reverse direction: undoes the change. Used for rollbacks. |
| **schema_migrations** | The tracking table maintained by the migration tool. Stores the current version and dirty flag. |
| **Dirty state** | When a migration fails partway through, leaving the database in an unknown state between two versions. Requires manual resolution with `force`. |
| **Expand-contract** | A zero-downtime pattern: add the new structure (expand), migrate application code, then remove the old structure (contract). |
| **Data migration** | A migration that changes data content (INSERT, UPDATE, DELETE) rather than schema structure. Kept separate from schema migrations. |
| **Backfill** | Populating a new column with values derived from existing data or business logic. |
| **Batched update** | Processing a large UPDATE in chunks to avoid long-running locks and transaction log bloat. |
| **Sequential naming** | Migration files numbered 000001, 000002, etc. Simple but collision-prone in teams. |
| **Timestamp naming** | Migration files prefixed with a timestamp (20260331143022). Avoids number collisions across branches. |
| **Online DDL** | Techniques for altering table structure without locking the entire table. Tools: pg_repack, gh-ost. |
| **FOR UPDATE SKIP LOCKED** | A PostgreSQL locking hint that skips rows already locked by other transactions, enabling concurrent batch processing. |
| **Declarative migration** | Defining the desired end-state schema and letting the tool compute the required ALTER statements. Opposite of versioned/imperative migrations. |
