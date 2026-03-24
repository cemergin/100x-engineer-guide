# L1-M18: Consistency Models in Practice

> **Loop 1 (Foundation)** | Section 1D: Architecture Fundamentals | Duration: 60 min | Tier: Core
>
> **Prerequisites:** L1-M17 (How Distributed Systems Fail)
>
> **What you'll build:** A Postgres primary + read replica setup, observe replication lag in real time, and implement a read-your-writes pattern in TicketPulse so users always see their own recent purchases.

---

## The Goal

In M17, you experienced what happens when components fail. Now we explore a subtler problem: what happens when components disagree.

You will set up two Postgres instances — a primary (handles writes) and a replica (handles reads). You will write data to the primary and immediately read from the replica. You will watch the replica return stale data. Then you will fix it.

This is not a theoretical exercise. Every production system with a read replica has this problem. Instagram, GitHub, Shopify — they all deal with replication lag. You will too.

**You will see stale data within the first five minutes.**

---

## 0. Quick Start: Primary + Replica Setup (5 minutes)

Update your `docker-compose.yml` to add a Postgres read replica:

```yaml
# docker-compose.yml (add these services)

services:
  postgres-primary:
    image: postgres:16
    container_name: ticketpulse-pg-primary
    environment:
      POSTGRES_USER: ticketpulse
      POSTGRES_PASSWORD: ticketpulse
      POSTGRES_DB: ticketpulse
    ports:
      - "5432:5432"
    volumes:
      - pg_primary_data:/var/lib/postgresql/data
      - ./docker/postgres/primary-init.sh:/docker-entrypoint-initdb.d/init.sh
    command: >
      postgres
        -c wal_level=replica
        -c max_wal_senders=3
        -c max_replication_slots=3
        -c hot_standby=on

  postgres-replica:
    image: postgres:16
    container_name: ticketpulse-pg-replica
    environment:
      POSTGRES_USER: ticketpulse
      POSTGRES_PASSWORD: ticketpulse
      POSTGRES_DB: ticketpulse
      PGUSER: replicator
      PGPASSWORD: replicator
    ports:
      - "5433:5432"
    depends_on:
      - postgres-primary
    volumes:
      - pg_replica_data:/var/lib/postgresql/data

volumes:
  pg_primary_data:
  pg_replica_data:
```

Create the primary initialization script:

```bash
# docker/postgres/primary-init.sh
#!/bin/bash
set -e

# Create replication user
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'replicator';
    SELECT pg_create_physical_replication_slot('replica_slot');
EOSQL

# Allow replication connections
echo "host replication replicator 0.0.0.0/0 md5" >> "$PGDATA/pg_hba.conf"
```

Set up the replica by taking a base backup from the primary:

```bash
# Start the primary first
docker compose up -d postgres-primary
sleep 5

# Take a base backup for the replica
docker exec ticketpulse-pg-primary pg_basebackup \
  -h localhost -U replicator -D /tmp/replica_backup \
  -Fp -Xs -P -R

# Copy the backup to the replica's data directory
docker cp ticketpulse-pg-primary:/tmp/replica_backup /tmp/pg_replica_data
docker compose up -d postgres-replica
```

Alternatively, use a simpler approach with a setup script:

```bash
# docker/postgres/setup-replication.sh
#!/bin/bash

echo "Starting primary..."
docker compose up -d postgres-primary
sleep 5

echo "Seeding data on primary..."
docker exec -i ticketpulse-pg-primary psql -U ticketpulse -d ticketpulse < ./seed.sql

echo "Setting up replica..."
# Remove old replica data
docker compose down postgres-replica
docker volume rm ticketpulse_pg_replica_data 2>/dev/null || true

# Create base backup
docker exec ticketpulse-pg-primary bash -c "
  rm -rf /tmp/replica_backup &&
  pg_basebackup -h localhost -U replicator -D /tmp/replica_backup -Fp -Xs -P -R -S replica_slot
"

# Start replica from backup
docker compose up -d postgres-replica
sleep 3

echo "Checking replication status..."
docker exec ticketpulse-pg-primary psql -U ticketpulse -d ticketpulse -c \
  "SELECT client_addr, state, sent_lsn, replay_lsn FROM pg_stat_replication;"

echo "Done! Primary on :5432, Replica on :5433"
```

```bash
chmod +x docker/postgres/setup-replication.sh
./docker/postgres/setup-replication.sh
```

Verify both are running:

```bash
# Connect to primary
docker exec -it ticketpulse-pg-primary psql -U ticketpulse -c "SELECT 'primary' AS role;"

# Connect to replica
docker exec -it ticketpulse-pg-replica psql -U ticketpulse -c "SELECT 'replica' AS role, pg_is_in_recovery();"
# pg_is_in_recovery should return TRUE (it's a replica)
```

---

## 1. See Replication in Action (10 minutes)

### 🔍 Try It: Write to Primary, Read from Replica

Open two terminals:

```bash
# Terminal 1: Connected to PRIMARY (port 5432)
docker exec -it ticketpulse-pg-primary psql -U ticketpulse -d ticketpulse

# Terminal 2: Connected to REPLICA (port 5433)
docker exec -it ticketpulse-pg-replica psql -U ticketpulse -d ticketpulse
```

**Terminal 1 (Primary) — Insert a new event:**

```sql
INSERT INTO events (title, venue, date, total_tickets, available_tickets, price_in_cents)
VALUES ('Replication Test Concert', 'The Lab', '2026-12-01T20:00:00Z', 100, 100, 7500)
RETURNING id, title;

-- Note the ID (let's say it's 42)
```

**Terminal 2 (Replica) — Read immediately:**

```sql
SELECT id, title FROM events WHERE title = 'Replication Test Concert';
```

Did it show up? In most cases with local Docker networking, yes — the replication lag is sub-millisecond. But this is deceiving. In production with network hops, load, and write-heavy workloads, lag can be seconds or even minutes.

### 🔍 Try It: Measure Replication Lag

**Terminal 1 (Primary):**

```sql
SELECT
  client_addr,
  state,
  sent_lsn,
  write_lsn,
  flush_lsn,
  replay_lsn,
  EXTRACT(EPOCH FROM (now() - write_lag)) AS write_lag_seconds,
  EXTRACT(EPOCH FROM (now() - flush_lag)) AS flush_lag_seconds,
  EXTRACT(EPOCH FROM (now() - replay_lag)) AS replay_lag_seconds
FROM pg_stat_replication;
```

This shows:
- `sent_lsn` vs `replay_lsn`: How far behind the replica is
- `write_lag_seconds`: Time for WAL data to reach the replica OS
- `flush_lag_seconds`: Time for WAL data to be flushed to replica disk
- `replay_lag_seconds`: Time for WAL data to be replayed on the replica

### 🔍 Try It: Create Visible Lag

Let us force replication lag by creating write pressure on the primary:

```sql
-- Terminal 1 (Primary): Insert 10,000 rows quickly
INSERT INTO events (title, venue, date, total_tickets, available_tickets, price_in_cents)
SELECT
  'Load Test Event ' || generate_series,
  'Venue ' || (generate_series % 10),
  '2026-12-01T20:00:00Z'::timestamptz + (generate_series || ' hours')::interval,
  100,
  100,
  5000 + (generate_series * 10)
FROM generate_series(1, 10000);
```

**Immediately** run on the replica:

```sql
-- Terminal 2 (Replica): Count events RIGHT NOW
SELECT COUNT(*) FROM events WHERE title LIKE 'Load Test Event%';
```

Run the count a few times in quick succession. You might see the count climbing as the replica catches up. That is eventual consistency happening before your eyes.

Check the lag again:

```sql
-- Terminal 1 (Primary):
SELECT
  replay_lag
FROM pg_stat_replication;
```

### Clean Up

```sql
-- Terminal 1 (Primary):
DELETE FROM events WHERE title LIKE 'Load Test Event%';
DELETE FROM events WHERE title = 'Replication Test Concert';
```

---

## 2. The Read-Your-Writes Problem (10 minutes)

Here is the scenario that breaks user experience:

1. User buys a ticket (write goes to primary)
2. User is redirected to "My Tickets" page (read goes to replica)
3. Replica has not received the write yet
4. User sees an empty page: "You have no tickets"
5. User panics, buys another ticket, gets double-charged

This is a real bug. It has happened at real companies. The fix is a pattern called **read-your-writes consistency.**

### 🔍 Try It: Simulate the Bug

```bash
# Step 1: Buy a ticket (writes to primary on :5432)
curl -s -X POST http://localhost:3000/api/events/1/tickets \
  -H 'Content-Type: application/json' \
  -d '{"email": "buyer@example.com"}' | jq '.data.id'

# Step 2: IMMEDIATELY read "my tickets" from the replica (:5433)
# (Simulating what happens when the app routes reads to the replica)
docker exec ticketpulse-pg-replica psql -U ticketpulse -d ticketpulse -c \
  "SELECT id, event_id, purchaser_email FROM tickets WHERE purchaser_email = 'buyer@example.com';"
```

If you are fast enough (or if there is any lag), the replica query returns zero rows even though the ticket was just purchased on the primary.

---

## 3. Build: Read-Your-Writes in TicketPulse (15 minutes)

### The Pattern

After a user writes data, route their subsequent reads to the primary for a short window (e.g., 5 seconds). After that window, the replica has caught up and reads can go back to the replica.

```
User writes (POST /tickets)
  │
  ├── Write goes to PRIMARY
  ├── Set session flag: "last_write_time = now"
  │
User reads (GET /my-tickets)
  │
  ├── Check: was last write within 5 seconds?
  │     │
  │     ├── YES → Read from PRIMARY (guaranteed fresh)
  │     │
  │     └── NO → Read from REPLICA (fast, eventually consistent)
```

### 🛠️ Build: Database Router

```typescript
// src/db/dbRouter.ts

import { Pool } from 'pg';

// Connection pools for primary and replica
const primaryPool = new Pool({
  host: process.env.DB_PRIMARY_HOST || 'localhost',
  port: parseInt(process.env.DB_PRIMARY_PORT || '5432'),
  database: 'ticketpulse',
  user: 'ticketpulse',
  password: 'ticketpulse',
  max: 10,
});

const replicaPool = new Pool({
  host: process.env.DB_REPLICA_HOST || 'localhost',
  port: parseInt(process.env.DB_REPLICA_PORT || '5433'),
  database: 'ticketpulse',
  user: 'ticketpulse',
  password: 'ticketpulse',
  max: 20, // More connections for reads
});

// Track recent writers by session/user ID
const recentWriters = new Map<string, number>(); // userId -> timestamp

const READ_YOUR_WRITES_WINDOW_MS = 5000; // 5 seconds

export function recordWrite(userId: string): void {
  recentWriters.set(userId, Date.now());

  // Clean up old entries every 100 writes
  if (recentWriters.size > 1000) {
    const cutoff = Date.now() - READ_YOUR_WRITES_WINDOW_MS;
    for (const [key, time] of recentWriters.entries()) {
      if (time < cutoff) recentWriters.delete(key);
    }
  }
}

export function getReadPool(userId?: string): Pool {
  if (!userId) {
    return replicaPool; // Anonymous reads go to replica
  }

  const lastWriteTime = recentWriters.get(userId);
  if (lastWriteTime && Date.now() - lastWriteTime < READ_YOUR_WRITES_WINDOW_MS) {
    console.log(`[db-router] User ${userId} wrote recently, routing to primary`);
    return primaryPool;
  }

  return replicaPool;
}

export function getWritePool(): Pool {
  return primaryPool; // All writes ALWAYS go to primary
}

// Stats for monitoring
let primaryReads = 0;
let replicaReads = 0;

export function getPoolForRead(userId?: string): Pool {
  const pool = getReadPool(userId);
  if (pool === primaryPool) {
    primaryReads++;
  } else {
    replicaReads++;
  }
  return pool;
}

export function getRoutingStats() {
  return {
    primaryReads,
    replicaReads,
    replicaPercentage: replicaReads / (primaryReads + replicaReads) || 0,
    recentWriters: recentWriters.size,
  };
}
```

### Wire Into the Ticket Purchase Flow

```typescript
// src/routes/tickets.ts (updated)

import { getWritePool, getPoolForRead, recordWrite } from '../db/dbRouter';

// POST /api/events/:id/tickets — always writes to primary
async function purchaseTicket(req: Request, res: Response) {
  const writePool = getWritePool();
  const userId = req.user?.id || req.body.email; // Identify the user

  const client = await writePool.connect();
  try {
    await client.query('BEGIN');

    // Check availability and reserve (on primary — strong consistency)
    const event = await client.query(
      'SELECT available_tickets FROM events WHERE id = $1 FOR UPDATE',
      [req.params.id]
    );

    if (event.rows[0].available_tickets < 1) {
      await client.query('ROLLBACK');
      return res.status(409).json({ error: { code: 'SOLD_OUT' } });
    }

    // Create ticket and decrement availability
    const ticket = await client.query(
      `INSERT INTO tickets (event_id, purchaser_email, status)
       VALUES ($1, $2, 'confirmed') RETURNING *`,
      [req.params.id, req.body.email]
    );

    await client.query(
      'UPDATE events SET available_tickets = available_tickets - 1 WHERE id = $1',
      [req.params.id]
    );

    await client.query('COMMIT');

    // Record that this user just wrote — their reads should go to primary
    recordWrite(userId);

    return res.status(201).json({ data: ticket.rows[0] });
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// GET /api/my-tickets — routes to primary if user wrote recently
async function getMyTickets(req: Request, res: Response) {
  const userId = req.user?.id || req.query.email;
  const readPool = getPoolForRead(userId as string);

  const tickets = await readPool.query(
    `SELECT t.id, t.event_id, t.status, t.created_at, e.title AS event_title
     FROM tickets t
     JOIN events e ON t.event_id = e.id
     WHERE t.purchaser_email = $1
     ORDER BY t.created_at DESC`,
    [userId]
  );

  return res.json({ data: tickets.rows });
}
```

### 🔍 Try It: Verify Read-Your-Writes

```bash
# Step 1: Buy a ticket
curl -s -X POST http://localhost:3000/api/events/1/tickets \
  -H 'Content-Type: application/json' \
  -d '{"email": "careful-buyer@example.com"}' | jq '.data.id'

# Step 2: IMMEDIATELY read my tickets (within 5-second window)
curl -s "http://localhost:3000/api/my-tickets?email=careful-buyer@example.com" | jq '.data'
# Should show the ticket! Reads are routed to primary.

# Step 3: Check the logs
# [db-router] User careful-buyer@example.com wrote recently, routing to primary

# Step 4: Wait 6 seconds and read again
sleep 6
curl -s "http://localhost:3000/api/my-tickets?email=careful-buyer@example.com" | jq '.data'
# Still shows the ticket, but now reads from replica (lag has caught up)
```

---

## 4. Observe: Traffic Split (5 minutes)

### 📊 Build a Routing Stats Endpoint

```typescript
// src/routes/health.ts

import { getRoutingStats } from '../db/dbRouter';

app.get('/api/debug/db-routing', (req, res) => {
  const stats = getRoutingStats();
  res.json({
    routing: stats,
    explanation: {
      primaryReads: 'Reads routed to primary (recent writers)',
      replicaReads: 'Reads routed to replica (normal traffic)',
      replicaPercentage: 'What percentage of reads go to the replica',
      recentWriters: 'Users currently in the read-your-writes window',
    },
  });
});
```

```bash
# After some traffic:
curl -s http://localhost:3000/api/debug/db-routing | jq
```

Expected output:

```json
{
  "routing": {
    "primaryReads": 3,
    "replicaReads": 47,
    "replicaPercentage": 0.94,
    "recentWriters": 1
  }
}
```

94% of reads go to the replica (taking load off the primary). Only the 6% from recent writers hit the primary for consistency. This is the ideal split.

---

## 5. Consistency Models Explained (10 minutes)

You have now experienced three consistency models firsthand. Let us name them.

### Strong Consistency (Linearizability)

Every read returns the most recent write. Period.

**Where you saw it:** Ticket purchase uses `SELECT ... FOR UPDATE` on the primary. The purchase flow is strongly consistent — you cannot oversell.

**Cost:** Higher latency. All reads and writes go to one server. Cannot horizontally scale reads.

**When to use:** Financial transactions, inventory management, anything where correctness is non-negotiable.

### Eventual Consistency

If you stop writing, eventually all reads will return the latest value. But there is a window where reads can be stale.

**Where you saw it:** Reading from the replica immediately after writing to the primary. The replica eventually catches up, but not instantly.

**Cost:** Application must tolerate stale data. Users might see confusing results (bought a ticket but "My Tickets" is empty).

**When to use:** High-read-volume endpoints where slight staleness is acceptable. Event listings, search results, analytics dashboards.

### Read-Your-Writes Consistency

A specific user always sees their own writes. Other users might see stale data, but the writer sees fresh data.

**Where you saw it:** The `dbRouter` that routes recent writers to the primary. After buying a ticket, that user reads from primary. Everyone else reads from the replica.

**Cost:** More complex routing logic. Primary handles more load from recent writers. Need to track write timestamps per user.

**When to use:** User-facing applications where "I just did X but I don't see it" is a common complaint. Social media posts, e-commerce purchases, profile updates.

### Causal Consistency

If event A caused event B, everyone sees A before B. Unrelated events can be seen in any order.

**TicketPulse example:** If Alice buys a ticket (event A) and then leaves a review (event B), all users must see the purchase before the review. But Bob's unrelated purchase can appear in any order relative to Alice's.

**Cost:** Requires tracking causal dependencies (vector clocks or similar). More complex than read-your-writes but weaker than strong consistency.

### Summary Table

| Model | TicketPulse Example | Staleness Window | Complexity | Use Case |
|-------|-------------------|-----------------|------------|----------|
| Strong | Ticket purchase | None | High | Inventory, payments |
| Read-your-writes | My Tickets page after purchase | None for the writer | Medium | User-facing after writes |
| Causal | Review after purchase | None for causal chain | Medium-High | Social features |
| Eventual | Event listing page | Seconds to minutes | Low | Browse, search, dashboards |

---

## 6. Reflect: Which TicketPulse Queries Need What? (5 minutes)

### 🤔 Exercise: Classify Every TicketPulse Endpoint

Fill in the consistency model for each:

| Endpoint | Consistency Needed | Why |
|----------|-------------------|-----|
| `GET /api/events` (listing) | ? | |
| `GET /api/events/:id` (detail) | ? | |
| `POST /api/events/:id/tickets` (purchase) | ? | |
| `GET /api/my-tickets` (after purchase) | ? | |
| `GET /api/my-tickets` (browsing later) | ? | |
| `GET /api/events/:id/availability` (seat count) | ? | |
| `POST /api/events` (create event, admin) | ? | |

**Suggested Answers:**

| Endpoint | Consistency Needed | Why |
|----------|-------------------|-----|
| `GET /api/events` | Eventual | Listing pages can tolerate 30s staleness |
| `GET /api/events/:id` | Eventual | Detail page cached with short TTL |
| `POST /api/events/:id/tickets` | Strong | Must not oversell — reads current inventory with `FOR UPDATE` |
| `GET /api/my-tickets` (just bought) | Read-your-writes | User expects to see their purchase immediately |
| `GET /api/my-tickets` (later) | Eventual | After 5s, replica has caught up |
| `GET /api/events/:id/availability` | Eventual (30s) | Approximate count is fine; purchase checks the real count |
| `POST /api/events` (admin) | Read-your-writes | Admin creates event and expects to see it in the list |

The default should be eventual consistency. Only upgrade to stronger models where the user experience or business logic demands it. Every upgrade costs performance.

---

## 7. Clean Up

```bash
# Remove the load test data if you haven't already
docker exec ticketpulse-pg-primary psql -U ticketpulse -d ticketpulse -c \
  "DELETE FROM events WHERE title LIKE 'Load Test Event%';"

# You can keep the primary/replica setup running for future modules
# Or tear it down:
# docker compose down postgres-replica
```

---

## 8. Checkpoint

After this module, TicketPulse should have:

- [ ] Postgres primary + replica running in docker compose
- [ ] Observed replication lag (even if sub-millisecond locally)
- [ ] Understood why reading from a replica immediately after writing can return stale data
- [ ] `dbRouter` that routes reads to primary or replica based on recent write activity
- [ ] Read-your-writes pattern: users always see their own purchases immediately
- [ ] Routing stats endpoint showing primary vs. replica traffic split
- [ ] Understanding of strong, eventual, read-your-writes, and causal consistency models
- [ ] Classification of every TicketPulse endpoint by consistency requirement

**Your TicketPulse should never show "You have no tickets" after a successful purchase.**

---

## Glossary

| Term | Definition |
|------|-----------|
| **Replication** | Copying data from one database instance (primary) to another (replica) to enable read scaling and fault tolerance. |
| **Primary** | The database instance that handles all writes. Also called leader or master. |
| **Replica** | A database instance that receives replicated data from the primary. Handles read queries. Also called follower or standby. |
| **Replication lag** | The delay between a write on the primary and that write being visible on the replica. Can be milliseconds to minutes. |
| **WAL (Write-Ahead Log)** | Postgres's transaction log. Streaming replication sends WAL records from primary to replica. |
| **Strong consistency** | Every read returns the most recent write. All observers see the same state. Requires coordination. |
| **Eventual consistency** | If no new writes occur, all replicas will eventually converge to the same state. No guarantee on timing. |
| **Read-your-writes** | A consistency guarantee that a user always sees their own writes, even if other users see stale data. |
| **Causal consistency** | If operation A caused operation B, all observers see A before B. Concurrent operations can be seen in any order. |
| **`pg_stat_replication`** | A Postgres system view that shows the status of all replication connections, including lag metrics. |

---

## Further Reading

- [PostgreSQL Streaming Replication](https://www.postgresql.org/docs/current/warm-standby.html) — Official documentation
- Martin Kleppmann, *Designing Data-Intensive Applications*, Chapter 5 (Replication)
- [How Shopify handles read-your-writes](https://shopify.engineering/read-consistency-taming-database-replication-lag) — Real-world pattern at scale
- Chapter 1 of the 100x Engineer Guide: Section 1.3 (Consistency Models)
