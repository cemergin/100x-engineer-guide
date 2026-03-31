# L2-M44b: Database Migrations as Code

> **Loop 2 (Practice)** | Section 2C: Infrastructure & Operations | ⏱️ 75 min | 🟢 Core | Prerequisites: L1-M06, L2-M44
>
> **Source:** Chapter 35 of the 100x Engineer Guide

## What You'll Learn

- Why database schema changes must be version-controlled migration files, not ad-hoc SQL
- Writing versioned migrations for TicketPulse: create, alter, index, and backfill
- The migration lifecycle: up, down, validate, and the migration table
- Zero-downtime migration patterns: expand-contract, backward-compatible changes
- Separating schema migrations from data migrations (and why it matters)
- Running and validating migrations in CI

## Why This Matters

TicketPulse's database schema has been evolving since L1-M05. You have created tables, added columns, and built indexes. But how did you make those changes? If you ran `CREATE TABLE` directly in psql, that change exists only in your local database. Your teammate's database is different. CI spins up a fresh database with no tables at all.

Migrations solve this: every schema change is a numbered file in Git. Running `migrate up` on any database — local, CI, staging, production — produces the same schema. The migration history IS the documentation. Rolling back a bad deploy means running `migrate down`, not guessing what SQL to undo.

## Prereq Check

```bash
# Ensure TicketPulse's PostgreSQL is running
docker compose up -d postgres
psql postgresql://localhost:5432/ticketpulse -c "SELECT 1"

# Install a migration tool (we'll use golang-migrate for its simplicity)
brew install golang-migrate
# OR: npm install -g prisma (if you prefer Prisma)
```

---

## 1. Your First Migration

Create a migrations directory and write your first versioned migration:

```bash
mkdir -p db/migrations
```

### Exercise 1: 🛠️ Build — Create the Migration Files

Write the migration pair for TicketPulse's events table:

```bash
# Create migration files (up + down)
migrate create -ext sql -dir db/migrations -seq create_events_table
```

This creates two files:

```sql
-- db/migrations/000001_create_events_table.up.sql
CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    venue       VARCHAR(255) NOT NULL,
    event_date  TIMESTAMP NOT NULL,
    capacity    INTEGER NOT NULL CHECK (capacity > 0),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_date ON events(event_date);
```

```sql
-- db/migrations/000001_create_events_table.down.sql
DROP TABLE IF EXISTS events;
```

Run the migration:

```bash
migrate -path db/migrations -database "postgresql://localhost:5432/ticketpulse?sslmode=disable" up
```

Write 3 more migration pairs:
1. `000002_create_tickets_table` — with a foreign key to events
2. `000003_add_email_to_tickets` — ALTER TABLE to add an email column
3. `000004_add_index_on_ticket_email` — CREATE INDEX for the new column

Run all migrations and verify:

```bash
migrate -path db/migrations -database "..." up
psql ticketpulse -c "\dt"        # List tables
psql ticketpulse -c "\di"        # List indexes
```

---

## 2. Migration Lifecycle

### Exercise 2: 🐛 Debug — Rollback and Recovery

Intentionally write a broken migration:

```sql
-- db/migrations/000005_bad_migration.up.sql
ALTER TABLE events ADD COLUMN foo INTEGR;  -- typo: INTEGR instead of INTEGER
```

Run `migrate up` and observe the failure. Now you are in a "dirty" state — the migration table shows version 5 as applied but it failed. Practice recovery:

```bash
# Check current version
migrate -path db/migrations -database "..." version

# Force the version back to the last successful migration
migrate -path db/migrations -database "..." force 4

# Fix the migration file, then re-run
migrate -path db/migrations -database "..." up
```

Then practice rollback:

```bash
# Roll back the last migration
migrate -path db/migrations -database "..." down 1

# Roll back to a specific version
migrate -path db/migrations -database "..." goto 2

# Roll back ALL migrations (fresh start)
migrate -path db/migrations -database "..." down
```

---

## 3. Zero-Downtime Patterns

### Exercise 3: 📐 Design — Expand-Contract Migration

TicketPulse needs to rename the `venue` column to `location` in the events table. You CANNOT do this:

```sql
ALTER TABLE events RENAME COLUMN venue TO location;  -- BREAKS running app!
```

The running application is still reading `venue`. Design the expand-contract migration sequence:

**Step 1 — Expand (deploy-safe):**

```sql
-- 000006_add_location_column.up.sql
ALTER TABLE events ADD COLUMN location VARCHAR(255);
UPDATE events SET location = venue WHERE location IS NULL;
```

**Step 2 — Update application code** to read from `location` and write to BOTH `venue` and `location`. Deploy.

**Step 3 — Contract (after all instances use `location`):**

```sql
-- 000007_drop_venue_column.up.sql
ALTER TABLE events DROP COLUMN venue;
```

Write all three migration files (up and down) and apply them in sequence. Verify at each step that the application could still function with the previous version of the code.

---

## 4. Data Migrations

### Exercise 4: 🛠️ Build — Separate Schema from Data

Write a data backfill migration for TicketPulse. Scenario: you need to add a `status` column to tickets with three possible values (`available`, `reserved`, `sold`). Existing tickets have no status.

Write THREE separate migrations:

```
000008_add_status_column.up.sql           -- Schema: ADD COLUMN status VARCHAR(20)
000009_backfill_ticket_status.up.sql      -- Data: UPDATE based on business logic
000010_make_status_not_null.up.sql        -- Schema: SET NOT NULL + CHECK constraint
```

Why three? If the backfill fails on 100K rows, the schema change is already committed. Separating them means you can retry just the data migration.

For the backfill, apply this logic:
- Tickets with a `payment_id` → `sold`
- Tickets with a `reserved_at` timestamp → `reserved`
- All others → `available`

---

## 5. CI Integration

### Exercise 5: 🚀 Deploy — Migrations in CI

Write a CI script (or Makefile target) that validates migrations:

```makefile
# Makefile
.PHONY: db-validate
db-validate:
	@echo "Starting clean database..."
	docker run -d --name migration-test -e POSTGRES_PASSWORD=test -p 5433:5432 postgres:16
	sleep 3
	@echo "Running all migrations..."
	migrate -path db/migrations \
	  -database "postgresql://postgres:test@localhost:5433/postgres?sslmode=disable" up
	@echo "Verifying schema..."
	psql postgresql://postgres:test@localhost:5433/postgres -c "\dt"
	@echo "Running all rollbacks..."
	migrate -path db/migrations \
	  -database "postgresql://postgres:test@localhost:5433/postgres?sslmode=disable" down
	@echo "Cleaning up..."
	docker rm -f migration-test
	@echo "✓ All migrations validated"
```

Run `make db-validate` and verify all migrations apply cleanly AND roll back cleanly on a fresh database.

### Exercise 6: 🤔 Reflect

Answer these questions in your notes:
1. What happens if two developers create `000006_*.sql` on different branches and both merge?
2. When would you choose a declarative tool (Atlas, Prisma Migrate) over a versioned tool (Flyway, golang-migrate)?
3. Should you ever edit an already-applied migration? Why or why not?
4. How does TicketPulse's migration workflow compare to Django's auto-generated migrations?
