# L2-M35: Database Per Service

> **Loop 2 (Practice)** | Section 2A: Breaking Apart the Monolith | ⏱️ 75 min | 🟢 Core | Prerequisites: L2-M31 (Strangler Fig), L2-M34 (Saga Pattern)
>
> **Source:** Chapters 3, 21, 25 of the 100x Engineer Guide

---

## The Goal

Right now, the monolith and the payment service share a single Postgres database. The payment service writes to the `payments` table. The monolith reads from it for order summaries. The order service JOINs `orders` with `events` with `payments` in a single query. Everything works because everything is in one database.

This defeats the purpose of microservices. If two services share a database:
- One service's schema migration can break the other
- One service's slow query can degrade the other's performance
- You cannot deploy or scale database resources independently
- The database is a hidden coupling point — services are not really independent

The goal of this module is to give each service its own database. This is widely considered the hardest part of a microservices migration. You will discover why.

By the end, each TicketPulse service will own its data completely. Cross-service queries will go through APIs. And you will implement the outbox pattern to reliably publish events when data changes.

**You will have separate databases running within five minutes. The hard part is everything after that.**

---

## 0. Design: Data Ownership Boundaries (10 minutes)

### 📐 Design Exercise

Look at TicketPulse's current database schema. Before reading the proposed split, decide for yourself: which tables belong to which service?

Here are the tables in the monolith's database:

```sql
-- Current schema (all in one database)
users (id, email, name, password_hash, created_at)
user_preferences (user_id, notification_channels, favorite_genres)

events (id, title, description, venue_id, date, capacity, status)
venues (id, name, address, city, capacity)
artists (id, name, genre)
event_artists (event_id, artist_id)

orders (id, user_id, event_id, ticket_id, payment_id, status, total_in_cents, created_at)
order_items (id, order_id, ticket_type, quantity, price_in_cents)

tickets (id, event_id, user_id, seat_number, tier, status)
reservations (id, ticket_id, user_id, expires_at, status)

payments (id, order_id, amount_in_cents, currency, status, payment_method, created_at)
refunds (id, payment_id, amount_in_cents, reason, status, created_at)
ledger_entries (id, payment_id, type, amount_in_cents, created_at)
```

### 🤔 Draw the Boundaries

For each table, assign it to one service. A table belongs to exactly one service — no sharing. Write down your answer before reading on.

Consider:
- Which service creates this data?
- Which service is the authority on this data?
- If two services need this data, who owns it and who gets a copy?

---

### The Proposed Split

```
┌─────────────────────┐  ┌─────────────────────┐
│  User Service DB    │  │  Event Service DB    │
│                     │  │                      │
│  users              │  │  events              │
│  user_preferences   │  │  venues              │
│                     │  │  artists             │
│                     │  │  event_artists       │
│                     │  │  tickets             │
│                     │  │  reservations        │
└─────────────────────┘  └──────────────────────┘

┌─────────────────────┐  ┌─────────────────────┐
│  Order Service DB   │  │  Payment Service DB  │
│                     │  │                      │
│  orders             │  │  payments            │
│  order_items        │  │  refunds             │
│                     │  │  ledger_entries      │
└─────────────────────┘  └──────────────────────┘
```

### Contested Decisions

Some assignments are obvious. Others require judgment:

**Tickets and reservations — Event Service or Order Service?**

Tickets are tied to events (capacity, seats, tiers). The event service manages availability. The order service cares about "which tickets did this user buy?" but does not manage seat assignments. Tickets belong to the event service. The order service stores a reference (`ticket_id`) and gets details via API.

**The `orders.event_id` and `orders.payment_id` columns — foreign keys to other services?**

These can no longer be foreign keys. They become opaque IDs. The order service stores them but cannot JOIN to get event details or payment status. It must call those services' APIs.

```sql
-- BEFORE (one database): a single query
SELECT o.id, o.status, e.title, e.date, p.status as payment_status
FROM orders o
JOIN events e ON o.event_id = e.id
JOIN payments p ON o.payment_id = p.id
WHERE o.user_id = $1;

-- AFTER (separate databases): this query is impossible
-- You must make three calls and combine the results
```

---

## 1. Build: Split the Databases (15 minutes)

### 🛠️ Update Docker Compose

```yaml
# docker-compose.yml — replace single postgres with per-service databases

services:
  # Remove the old single postgres, add these:

  postgres-events:
    image: postgres:16-alpine
    container_name: ticketpulse-db-events
    environment:
      POSTGRES_DB: ticketpulse_events
      POSTGRES_USER: events_svc
      POSTGRES_PASSWORD: events_pass
    ports:
      - "5432:5432"
    volumes:
      - pg_events_data:/var/lib/postgresql/data
      - ./db/migrations/events:/docker-entrypoint-initdb.d

  postgres-orders:
    image: postgres:16-alpine
    container_name: ticketpulse-db-orders
    environment:
      POSTGRES_DB: ticketpulse_orders
      POSTGRES_USER: orders_svc
      POSTGRES_PASSWORD: orders_pass
    ports:
      - "5433:5432"
    volumes:
      - pg_orders_data:/var/lib/postgresql/data
      - ./db/migrations/orders:/docker-entrypoint-initdb.d

  postgres-payments:
    image: postgres:16-alpine
    container_name: ticketpulse-db-payments
    environment:
      POSTGRES_DB: ticketpulse_payments
      POSTGRES_USER: payments_svc
      POSTGRES_PASSWORD: payments_pass
    ports:
      - "5434:5432"
    volumes:
      - pg_payments_data:/var/lib/postgresql/data
      - ./db/migrations/payments:/docker-entrypoint-initdb.d

  postgres-users:
    image: postgres:16-alpine
    container_name: ticketpulse-db-users
    environment:
      POSTGRES_DB: ticketpulse_users
      POSTGRES_USER: users_svc
      POSTGRES_PASSWORD: users_pass
    ports:
      - "5435:5432"
    volumes:
      - pg_users_data:/var/lib/postgresql/data
      - ./db/migrations/users:/docker-entrypoint-initdb.d

volumes:
  pg_events_data:
  pg_orders_data:
  pg_payments_data:
  pg_users_data:
```

### Create Migration Scripts

```bash
mkdir -p db/migrations/{events,orders,payments,users}
```

```sql
-- db/migrations/events/001_init.sql

CREATE TABLE events (
  id SERIAL PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  venue_id INTEGER NOT NULL,
  date TIMESTAMP NOT NULL,
  capacity INTEGER NOT NULL,
  status VARCHAR(50) DEFAULT 'draft',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE venues (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  address TEXT,
  city VARCHAR(100),
  capacity INTEGER
);

CREATE TABLE artists (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  genre VARCHAR(100)
);

CREATE TABLE event_artists (
  event_id INTEGER REFERENCES events(id),
  artist_id INTEGER REFERENCES artists(id),
  PRIMARY KEY (event_id, artist_id)
);

CREATE TABLE tickets (
  id SERIAL PRIMARY KEY,
  event_id INTEGER REFERENCES events(id),
  user_id INTEGER NOT NULL,  -- No FK — user lives in another database
  seat_number VARCHAR(20),
  tier VARCHAR(50) DEFAULT 'general',
  status VARCHAR(50) DEFAULT 'available',
  price_in_cents INTEGER NOT NULL
);

CREATE TABLE reservations (
  id SERIAL PRIMARY KEY,
  ticket_id INTEGER REFERENCES tickets(id),
  user_id INTEGER NOT NULL,  -- No FK
  expires_at TIMESTAMP NOT NULL,
  status VARCHAR(50) DEFAULT 'active'
);

-- Seed data
INSERT INTO venues (name, address, city, capacity) VALUES
  ('Madison Square Garden', '4 Pennsylvania Plaza', 'New York', 20000),
  ('The Fillmore', '1805 Geary Blvd', 'San Francisco', 1150);

INSERT INTO events (title, venue_id, date, capacity, status) VALUES
  ('Taylor Swift - Eras Tour', 1, '2026-06-15 20:00:00', 20000, 'published'),
  ('Radiohead - Reunion', 2, '2026-07-20 19:30:00', 1150, 'published'),
  ('Jazz Night at The Fillmore', 2, '2026-08-01 21:00:00', 500, 'published');
```

```sql
-- db/migrations/orders/001_init.sql

CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,      -- No FK — user lives in another database
  event_id INTEGER NOT NULL,     -- No FK — event lives in another database
  ticket_id INTEGER NOT NULL,    -- No FK — ticket lives in another database
  payment_id VARCHAR(100),       -- No FK — payment lives in another database
  status VARCHAR(50) DEFAULT 'pending',
  total_in_cents INTEGER NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE order_items (
  id SERIAL PRIMARY KEY,
  order_id INTEGER REFERENCES orders(id),
  ticket_type VARCHAR(50),
  quantity INTEGER DEFAULT 1,
  price_in_cents INTEGER NOT NULL
);
```

```sql
-- db/migrations/payments/001_init.sql

CREATE TABLE payments (
  id VARCHAR(100) PRIMARY KEY,
  order_id VARCHAR(100) NOT NULL UNIQUE,  -- Idempotency key
  amount_in_cents INTEGER NOT NULL,
  currency VARCHAR(3) DEFAULT 'USD',
  status VARCHAR(50) DEFAULT 'pending',
  payment_method VARCHAR(50),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE refunds (
  id VARCHAR(100) PRIMARY KEY,
  payment_id VARCHAR(100) REFERENCES payments(id),
  amount_in_cents INTEGER NOT NULL,
  reason TEXT,
  status VARCHAR(50) DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ledger_entries (
  id SERIAL PRIMARY KEY,
  payment_id VARCHAR(100) REFERENCES payments(id),
  type VARCHAR(50) NOT NULL,  -- 'charge', 'refund', 'fee'
  amount_in_cents INTEGER NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);
```

```sql
-- db/migrations/users/001_init.sql

CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(255),
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_preferences (
  user_id INTEGER REFERENCES users(id) PRIMARY KEY,
  notification_channels JSONB DEFAULT '["email"]',
  favorite_genres TEXT[] DEFAULT '{}'
);

-- Seed data
INSERT INTO users (email, name, password_hash) VALUES
  ('alice@example.com', 'Alice', '$2b$10$dummy_hash_for_development');
```

### 🚀 Deploy

```bash
docker compose up -d postgres-events postgres-orders postgres-payments postgres-users

# Verify all databases are running
docker compose ps | grep postgres
```

You should see four Postgres containers, each on a different port:

```
ticketpulse-db-events     running  0.0.0.0:5432->5432/tcp
ticketpulse-db-orders     running  0.0.0.0:5433->5432/tcp
ticketpulse-db-payments   running  0.0.0.0:5434->5432/tcp
ticketpulse-db-users      running  0.0.0.0:5435->5432/tcp
```

### Update Service Connection Strings

```yaml
# docker-compose.yml — update service environment variables

  monolith:
    environment:
      # The monolith connects to events and orders databases
      # (User service will be extracted later)
      EVENTS_DATABASE_URL: postgresql://events_svc:events_pass@postgres-events:5432/ticketpulse_events
      ORDERS_DATABASE_URL: postgresql://orders_svc:orders_pass@postgres-orders:5432/ticketpulse_orders
      USERS_DATABASE_URL: postgresql://users_svc:users_pass@postgres-users:5432/ticketpulse_users

  payment-service:
    environment:
      DATABASE_URL: postgresql://payments_svc:payments_pass@postgres-payments:5432/ticketpulse_payments
```

---

## 2. Debug: The Broken Query (15 minutes)

### 🐛 The "My Orders" Page

Before the split, the "my orders" endpoint looked like this:

```typescript
// BEFORE: One query, one database
async function getMyOrders(userId: string) {
  const result = await db.query(`
    SELECT
      o.id, o.status, o.total_in_cents, o.created_at,
      e.title as event_title, e.date as event_date,
      v.name as venue_name,
      p.status as payment_status
    FROM orders o
    JOIN events e ON o.event_id = e.id
    JOIN venues v ON e.venue_id = v.id
    JOIN payments p ON o.payment_id = p.id
    WHERE o.user_id = $1
    ORDER BY o.created_at DESC
  `, [userId]);

  return result.rows;
}
```

One query. Four tables. Clean, fast, simple. This query is now **impossible** — the tables live in different databases.

### 🛠️ Build: The Replacement

You must replace the JOIN with multiple API calls and combine the results in application code:

```typescript
// AFTER: Multiple API calls, application-level join

async function getMyOrders(userId: string) {
  // Step 1: Get orders from the order database
  const orders = await ordersDb.query(
    'SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC',
    [userId]
  );

  if (orders.rows.length === 0) return [];

  // Step 2: Collect unique event IDs and payment IDs
  const eventIds = [...new Set(orders.rows.map(o => o.event_id))];
  const paymentIds = orders.rows.map(o => o.payment_id).filter(Boolean);

  // Step 3: Fetch event details from the event service (batch call)
  const eventsResponse = await fetch(
    `${EVENT_SERVICE_URL}/api/events?ids=${eventIds.join(',')}`
  );
  const events = await eventsResponse.json();
  const eventMap = new Map(events.data.map((e: any) => [e.id, e]));

  // Step 4: Fetch payment statuses from the payment service (batch call)
  const paymentsResponse = await fetch(
    `${PAYMENT_SERVICE_URL}/api/payments?ids=${paymentIds.join(',')}`
  );
  const payments = await paymentsResponse.json();
  const paymentMap = new Map(payments.data.map((p: any) => [p.id, p]));

  // Step 5: Combine in application code
  return orders.rows.map(order => {
    const event = eventMap.get(order.event_id);
    const payment = paymentMap.get(order.payment_id);

    return {
      id: order.id,
      status: order.status,
      totalInCents: order.total_in_cents,
      createdAt: order.created_at,
      eventTitle: event?.title || 'Unknown Event',
      eventDate: event?.date || null,
      venueName: event?.venue?.name || 'Unknown Venue',
      paymentStatus: payment?.status || 'unknown',
    };
  });
}
```

### What Just Happened

| Aspect | Before (JOIN) | After (API calls) |
|--------|---------------|-------------------|
| Database queries | 1 | 1 (orders) |
| Network calls | 0 | 2 (events API, payments API) |
| Latency | ~5ms | ~50-100ms |
| Consistency | Point-in-time snapshot | Eventually consistent (data may change between calls) |
| Code complexity | 10 lines SQL | 40 lines TypeScript |
| Failure modes | 1 (DB down) | 3 (DB down, event svc down, payment svc down) |

This is the real cost of database-per-service. It is not free. It trades simplicity and performance for independence and scalability.

### Optimize: Batch API Endpoints

Notice we made batch calls (`/api/events?ids=1,2,3`) instead of calling each event individually. Always design batch endpoints when you split databases — the alternative is N+1 API calls.

```typescript
// services/event-service — add batch endpoint
app.get('/api/events', (req, res) => {
  const ids = req.query.ids?.split(',').map(Number);
  if (!ids || ids.length === 0) {
    return res.status(400).json({ error: 'ids query parameter required' });
  }

  // Limit batch size to prevent abuse
  if (ids.length > 100) {
    return res.status(400).json({ error: 'Maximum 100 IDs per batch' });
  }

  const events = await eventsDb.query(
    'SELECT * FROM events WHERE id = ANY($1)',
    [ids]
  );

  res.json({ data: events.rows });
});
```

---

## 3. The Outbox Pattern (15 minutes)

### The Problem

When the payment service processes a payment, it needs to:
1. Write the payment record to its database
2. Publish a `PaymentProcessed` event to Kafka

What if the database write succeeds but the Kafka publish fails? The payment exists but no event was sent. The order service never finds out. The customer sees "payment pending" forever.

What if the Kafka publish succeeds but the database write fails (or is rolled back)? An event says "payment processed" but the payment does not exist.

### The Solution: Outbox Pattern

Write the event to an **outbox table** in the same database transaction as the business data. A separate process reads the outbox and publishes to Kafka.

```
┌─────────────────────────────────────────┐
│ Payment Service Database                 │
│                                          │
│  BEGIN TRANSACTION;                      │
│    INSERT INTO payments (...);           │
│    INSERT INTO outbox (topic, payload);  │  ← Same transaction
│  COMMIT;                                 │
│                                          │
│  outbox table:                           │
│  ┌──────────────────────────────────┐    │
│  │ id │ topic    │ payload │ sent  │    │
│  │ 1  │ payments │ {...}   │ false │    │
│  │ 2  │ payments │ {...}   │ false │    │
│  └──────────────────────────────────┘    │
└──────────────────┬───────────────────────┘
                   │
                   │ Outbox Publisher (polls or CDC)
                   │
                   ▼
              ┌─────────┐
              │  Kafka   │
              └─────────┘
```

Both the business data and the event are written in one transaction. Either both succeed or both fail. The outbox publisher is a separate process that reads unsent events and publishes them to Kafka.

### 🛠️ Build: The Outbox

```sql
-- db/migrations/payments/002_outbox.sql

CREATE TABLE outbox (
  id BIGSERIAL PRIMARY KEY,
  aggregate_type VARCHAR(100) NOT NULL,  -- e.g., 'Payment'
  aggregate_id VARCHAR(100) NOT NULL,    -- e.g., 'pay_abc123'
  event_type VARCHAR(100) NOT NULL,      -- e.g., 'PaymentProcessed'
  topic VARCHAR(100) NOT NULL,           -- e.g., 'ticket-purchases'
  payload JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  published_at TIMESTAMP NULL            -- NULL = not yet published
);

CREATE INDEX idx_outbox_unpublished ON outbox (created_at) WHERE published_at IS NULL;
```

```typescript
// services/payment-service/src/outbox.ts

import { Pool } from 'pg';

const db = new Pool({
  connectionString: process.env.DATABASE_URL,
});

export async function processPaymentWithOutbox(
  orderId: string,
  amountInCents: number,
  currency: string,
  paymentMethod: string
): Promise<any> {
  const client = await db.connect();

  try {
    await client.query('BEGIN');

    // Step 1: Insert the payment
    const paymentId = `pay_${Date.now()}`;
    await client.query(
      `INSERT INTO payments (id, order_id, amount_in_cents, currency, status, payment_method)
       VALUES ($1, $2, $3, $4, 'completed', $5)`,
      [paymentId, orderId, amountInCents, currency, paymentMethod]
    );

    // Step 2: Insert the ledger entry
    await client.query(
      `INSERT INTO ledger_entries (payment_id, type, amount_in_cents)
       VALUES ($1, 'charge', $2)`,
      [paymentId, amountInCents]
    );

    // Step 3: Insert the outbox event (SAME TRANSACTION)
    await client.query(
      `INSERT INTO outbox (aggregate_type, aggregate_id, event_type, topic, payload)
       VALUES ($1, $2, $3, $4, $5)`,
      [
        'Payment',
        paymentId,
        'PaymentProcessed',
        'ticket-purchases',
        JSON.stringify({
          type: 'PaymentProcessed',
          occurredAt: new Date().toISOString(),
          payload: {
            paymentId,
            orderId,
            amountInCents,
            currency,
            status: 'completed',
          },
        }),
      ]
    );

    await client.query('COMMIT');

    console.log(`[payment] Payment ${paymentId} and outbox event committed in one transaction`);
    return { id: paymentId, orderId, amountInCents, currency, status: 'completed' };

  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}
```

### 🛠️ Build: The Outbox Publisher

```typescript
// services/payment-service/src/outboxPublisher.ts

import { Pool } from 'pg';
import { Kafka } from 'kafkajs';

const db = new Pool({ connectionString: process.env.DATABASE_URL });
const kafka = new Kafka({
  clientId: 'payment-outbox-publisher',
  brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
});
const producer = kafka.producer();

const POLL_INTERVAL = 1000; // 1 second

async function publishOutboxEvents(): Promise<void> {
  const client = await db.connect();

  try {
    // Select unpublished events, oldest first
    const result = await client.query(
      `SELECT * FROM outbox
       WHERE published_at IS NULL
       ORDER BY created_at ASC
       LIMIT 100
       FOR UPDATE SKIP LOCKED`  // Lock rows to prevent duplicate publishing
    );

    if (result.rows.length === 0) return;

    for (const row of result.rows) {
      try {
        await producer.send({
          topic: row.topic,
          messages: [{
            key: row.aggregate_id,
            value: row.payload,
            headers: {
              'event-type': row.event_type,
              'aggregate-type': row.aggregate_type,
              'outbox-id': String(row.id),
            },
          }],
        });

        // Mark as published
        await client.query(
          'UPDATE outbox SET published_at = NOW() WHERE id = $1',
          [row.id]
        );

        console.log(`[outbox] Published event ${row.id}: ${row.event_type}`);
      } catch (err) {
        console.error(`[outbox] Failed to publish event ${row.id}:`, (err as Error).message);
        // Don't mark as published — will retry on next poll
      }
    }
  } finally {
    client.release();
  }
}

async function start(): Promise<void> {
  await producer.connect();
  console.log('[outbox-publisher] Connected to Kafka');

  // Poll for new events
  setInterval(publishOutboxEvents, POLL_INTERVAL);
  console.log(`[outbox-publisher] Polling every ${POLL_INTERVAL}ms`);
}

start().catch(err => {
  console.error('[outbox-publisher] Failed to start:', err);
  process.exit(1);
});
```

The `FOR UPDATE SKIP LOCKED` clause is critical — it prevents two publisher instances from publishing the same event, enabling safe horizontal scaling of the publisher.

---

## 4. Reflect (10 minutes)

### 🤔 What Was the Hardest Query to Split?

Think about all the queries in TicketPulse that crossed table boundaries. Which ones were hardest to decompose?

Common answers:
- **"My orders" page** — needs data from orders, events, venues, and payments
- **Event detail page** — needs event info, artist info, ticket availability, and user's existing reservations
- **Admin dashboard** — needs aggregate data from every service
- **Search** — needs to search across events, artists, venues, and availability

### 🤔 Is the Complexity Worth the Independence?

The honest assessment:

| Gained | Lost |
|--------|------|
| Independent deployments per service | Simple JOINs |
| Independent scaling per database | Transactional consistency |
| Schema isolation (no accidental breakage) | Single-query data views |
| Clear data ownership | Development speed (more code for the same feature) |
| Ability to use different DB tech per service | Operational simplicity |

For a team of 3 engineers with one product: probably not worth it. The overhead is significant.

For a team of 30 engineers with multiple squads each owning services: essential. The coordination cost of a shared database exceeds the complexity cost of APIs.

### CDC as an Alternative

Instead of API calls for read-heavy cross-service queries, you can use **Change Data Capture (CDC)** with tools like Debezium:

```
Event Service DB ──CDC──→ Kafka ──→ Order Service DB
                                    (read-only copy of events table)
```

The order service maintains a local, read-only copy of the events table. Updated in near-real-time via CDC. Cross-service JOINs work again, but with eventual consistency. This is a common production pattern for read-heavy queries.

---

## 5. Checkpoint

After this module, TicketPulse should have:

- [ ] Four Postgres instances running in docker compose (events, orders, payments, users)
- [ ] Migration scripts for each database with appropriate tables
- [ ] No foreign keys across service boundaries — only opaque IDs
- [ ] The "my orders" query replaced with API calls + application-level join
- [ ] Batch API endpoints to avoid N+1 call patterns
- [ ] The outbox pattern implemented in the payment service
- [ ] An outbox publisher process that polls and publishes events to Kafka
- [ ] Understanding of why database-per-service is hard and when it is worth the cost

---

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **Database per service** | Each service owns its database. No shared tables. Cross-service data access goes through APIs. |
| **Data ownership** | Every piece of data has exactly one authoritative owner. Other services store references (IDs) and fetch details via API. |
| **Application-level join** | When a JOIN crosses service boundaries, it becomes multiple API calls combined in application code. Slower but decoupled. |
| **Batch endpoints** | Design APIs that accept multiple IDs to avoid N+1 call patterns. |
| **Outbox pattern** | Write business data and event to the same transaction. A separate publisher reads the outbox and publishes to the message broker. Guarantees at-least-once event delivery. |
| **CDC (Change Data Capture)** | Stream database changes to other services. Useful for maintaining read-only copies across service boundaries. |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Database per service** | An architecture pattern where each microservice has its own private database that no other service can access directly. |
| **Data ownership** | The principle that each piece of data has exactly one service that is the authoritative source of truth. |
| **Application-level join** | Combining data from multiple services in application code rather than a database JOIN. Requires multiple API calls. |
| **Outbox pattern** | A pattern where domain events are written to an outbox table in the same transaction as business data, then asynchronously published to a message broker. |
| **Change Data Capture (CDC)** | A technique for streaming changes from a database to other systems. Tools like Debezium capture INSERT/UPDATE/DELETE events from the database's transaction log. |
| **Debezium** | An open-source CDC platform that streams changes from databases (Postgres, MySQL, MongoDB) to Kafka topics. |
| **FOR UPDATE SKIP LOCKED** | A Postgres clause that locks selected rows and skips rows already locked by other transactions. Used to safely distribute work across multiple publisher instances. |

---

## Further Reading

- Sam Newman, *Building Microservices*, Chapter 4 (Splitting the Monolith's Database)
- [Outbox Pattern](https://microservices.io/patterns/data/transactional-outbox.html) — Microservices.io pattern description
- [Debezium Documentation](https://debezium.io/documentation/) — CDC for Postgres, MySQL, MongoDB
- Martin Kleppmann, *Designing Data-Intensive Applications*, Chapter 11 (Change Data Capture)
- Chapter 3 of the 100x Engineer Guide: Section 6 (Data Ownership)
