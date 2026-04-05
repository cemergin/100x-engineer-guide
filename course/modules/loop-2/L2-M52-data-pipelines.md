# L2-M52: Data Pipelines

> **Loop 2 (Practice)** | Section 2D: Advanced Patterns | ⏱️ 75 min | 🟡 Deep Dive | Prerequisites: L2-M39 (Kubernetes Basics), L2-M44 (Kafka Basics or equivalent)
>
> **Source:** Chapters 3, 22, 25, 32, 13 of the 100x Engineer Guide

> **Before you continue:** TicketPulse stores ticket sales in Postgres, search data in Elasticsearch, and events in Kafka. The analytics team wants all of this in a data warehouse for reporting. How would you move data from multiple operational systems into a single analytics store reliably?

---

## The Goal

TicketPulse needs analytics: daily revenue, popular events, user cohort analysis, conversion funnels. Today, someone runs ad-hoc SQL queries against the production database. This is bad for three reasons:

1. **Performance**: Analytics queries (aggregations, full table scans) compete with production queries (fast point lookups). A reporting query that scans 10M orders slows down every checkout.
2. **Schema coupling**: The analytics team cannot reshape the data without coordinating with the application team. They are stuck with the application's normalized schema.
3. **Freshness vs safety**: Running heavy queries directly on prod means choosing between stale data (use a replica) and risk (hit the primary).

The solution: stream changes out of the production database, transform them, and load them into a separate analytics store. The production database is never touched by analytics queries.

**You will run code within the first two minutes.**

---

## 0. Design: The Pipeline Architecture (10 minutes)

```
┌─────────────┐    CDC     ┌─────────┐  stream  ┌──────────────┐  write  ┌────────────┐
│  TicketPulse │ ────────► │  Kafka   │ ──────► │  Consumer /   │ ──────► │  Analytics  │
│  Postgres    │  Debezium  │  Topics  │          │  Transformer  │         │  Database   │
└─────────────┘            └─────────┘          └──────────────┘         └────────────┘
```

**Source**: TicketPulse's Postgres database (events, orders, tickets, users tables)

**Capture**: Debezium reads the Postgres write-ahead log (WAL). Every INSERT, UPDATE, DELETE is captured as an event -- no application code changes needed, no performance impact on the application.

**Transport**: Kafka topics, one per table (`ticketpulse.public.orders`, `ticketpulse.public.events`, etc.)

**Transform**: A consumer reads the change events, denormalizes them (joins order data with event and user data), and writes to the analytics schema.

**Load**: A separate Postgres database (or ClickHouse for large-scale analytics) with a schema optimized for queries, not transactions.

> **Your decision:** What should the analytics database be?
>
> - **Separate Postgres instance**: Simplest operationally. Good enough for most startups. Use materialized views for common aggregations.
> - **ClickHouse**: Columnar storage, extremely fast for aggregation queries over millions of rows. More operational overhead.
> - **BigQuery/Redshift**: Managed, scales massively, but adds cloud vendor coupling and cost.
>
> Start with a separate Postgres instance. Migrate to a columnar store when query volume or data size demands it.

---

## 1. Build: Set Up Debezium (15 minutes)

Debezium runs as a Kafka Connect connector. First, configure Postgres for logical replication:

```sql
-- On the TicketPulse Postgres instance
-- Enable logical replication (requires restart if not already set)
ALTER SYSTEM SET wal_level = logical;

-- Create a replication slot for Debezium
SELECT pg_create_logical_replication_slot('debezium_slot', 'pgoutput');

-- Grant replication permissions to the Debezium user
CREATE ROLE debezium_user WITH REPLICATION LOGIN PASSWORD 'debezium_pass';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium_user;
```

Add Debezium to the Docker Compose stack:

```yaml
# docker-compose.analytics.yml

services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on: [zookeeper]
    ports: ["9092:9092"]
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

  kafka-connect:
    image: debezium/connect:2.4
    depends_on: [kafka]
    ports: ["8083:8083"]
    environment:
      BOOTSTRAP_SERVERS: kafka:9092
      GROUP_ID: ticketpulse-connect
      CONFIG_STORAGE_TOPIC: connect-configs
      OFFSET_STORAGE_TOPIC: connect-offsets
      STATUS_STORAGE_TOPIC: connect-status
      CONFIG_STORAGE_REPLICATION_FACTOR: 1
      OFFSET_STORAGE_REPLICATION_FACTOR: 1
      STATUS_STORAGE_REPLICATION_FACTOR: 1

  analytics-db:
    image: postgres:16
    ports: ["5433:5432"]
    environment:
      POSTGRES_DB: ticketpulse_analytics
      POSTGRES_USER: analytics
      POSTGRES_PASSWORD: analytics_pass
    volumes:
      - analytics-data:/var/lib/postgresql/data

volumes:
  analytics-data:
```

> ⚠️ **Version Note:** This module pins specific software versions that were current at writing (March 2026). Before running, check for the latest stable releases — Docker images, package versions, and tool versions evolve frequently. The concepts and patterns remain the same regardless of version.

Start the stack:

```bash
docker compose -f docker-compose.analytics.yml up -d
```

Register the Debezium connector:

```bash
curl -X POST http://localhost:8083/connectors \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "ticketpulse-connector",
    "config": {
      "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
      "database.hostname": "ticketpulse-db",
      "database.port": "5432",
      "database.user": "debezium_user",
      "database.password": "debezium_pass",
      "database.dbname": "ticketpulse",
      "topic.prefix": "ticketpulse",
      "table.include.list": "public.orders,public.events,public.tickets,public.users",
      "slot.name": "debezium_slot",
      "plugin.name": "pgoutput",
      "publication.name": "ticketpulse_publication",
      "key.converter": "org.apache.kafka.connect.json.JsonConverter",
      "value.converter": "org.apache.kafka.connect.json.JsonConverter",
      "key.converter.schemas.enable": false,
      "value.converter.schemas.enable": false
    }
  }'
```

Verify the connector is running:

```bash
curl http://localhost:8083/connectors/ticketpulse-connector/status | jq .
```

---

## 2. Build: The Analytics Consumer (20 minutes)

Set up the analytics database schema:

```sql
-- On the analytics database (port 5433)

-- Denormalized order facts -- one row per order, all dimensions pre-joined
CREATE TABLE order_facts (
  order_id        TEXT PRIMARY KEY,
  event_id        TEXT NOT NULL,
  event_name      TEXT,
  venue_city      TEXT,
  user_id         TEXT NOT NULL,
  user_email      TEXT,
  ticket_type     TEXT NOT NULL,
  quantity        INTEGER NOT NULL,
  total_cents     INTEGER NOT NULL,
  status          TEXT NOT NULL,
  ordered_at      TIMESTAMPTZ NOT NULL,
  updated_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_order_facts_event ON order_facts(event_id);
CREATE INDEX idx_order_facts_ordered_at ON order_facts(ordered_at);
CREATE INDEX idx_order_facts_status ON order_facts(status);

-- Materialized view: daily revenue
CREATE MATERIALIZED VIEW daily_revenue AS
SELECT
  date_trunc('day', ordered_at) AS day,
  COUNT(*) AS order_count,
  SUM(quantity) AS tickets_sold,
  SUM(total_cents) AS revenue_cents,
  COUNT(DISTINCT user_id) AS unique_buyers,
  COUNT(DISTINCT event_id) AS events_with_sales
FROM order_facts
WHERE status = 'confirmed'
GROUP BY date_trunc('day', ordered_at)
ORDER BY day DESC;

CREATE UNIQUE INDEX idx_daily_revenue_day ON daily_revenue(day);
```

Now the consumer that reads from Kafka and writes to the analytics DB:

```typescript
// src/analytics/cdc-consumer.ts

import { Kafka, Consumer, EachMessagePayload } from 'kafkajs';
import { Pool } from 'pg';

const kafka = new Kafka({ brokers: ['localhost:9092'] });
const analyticsDb = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'ticketpulse_analytics',
  user: 'analytics',
  password: 'analytics_pass',
});

// In-memory cache for denormalization lookups
// In production, use Redis or a local cache with TTL
const eventCache = new Map<string, { name: string; venueCity: string }>();
const userCache = new Map<string, { email: string }>();

export class CdcConsumer {
  private consumer: Consumer;

  constructor() {
    this.consumer = kafka.consumer({ groupId: 'analytics-consumer' });
  }

  async start(): Promise<void> {
    await this.consumer.connect();
    await this.consumer.subscribe({
      topics: [
        'ticketpulse.public.orders',
        'ticketpulse.public.events',
        'ticketpulse.public.users',
      ],
      fromBeginning: true,
    });

    await this.consumer.run({
      eachMessage: async (payload: EachMessagePayload) => {
        const { topic, message } = payload;
        if (!message.value) return;

        const change = JSON.parse(message.value.toString());
        const tableName = topic.split('.').pop();

        console.log(`[cdc] Processing ${change.op} on ${tableName}`);

        switch (tableName) {
          case 'orders':
            await this.handleOrderChange(change);
            break;
          case 'events':
            await this.handleEventChange(change);
            break;
          case 'users':
            await this.handleUserChange(change);
            break;
        }
      },
    });

    console.log('[cdc] Consumer started, listening for changes...');
  }

  private async handleOrderChange(change: DebeziumChange): Promise<void> {
    // Debezium change event structure:
    // op: 'c' (create), 'u' (update), 'd' (delete), 'r' (read/snapshot)
    // before: row state before the change (null for inserts)
    // after: row state after the change (null for deletes)

    if (change.op === 'd') {
      // Soft delete in analytics -- update status
      await analyticsDb.query(
        'UPDATE order_facts SET status = $1, updated_at = NOW() WHERE order_id = $2',
        ['deleted', change.before.id]
      );
      return;
    }

    const row = change.after;

    // Denormalize: look up event and user details
    const eventInfo = await this.getEventInfo(row.event_id);
    const userInfo = await this.getUserInfo(row.user_id);

    await analyticsDb.query(
      `INSERT INTO order_facts
        (order_id, event_id, event_name, venue_city, user_id, user_email,
         ticket_type, quantity, total_cents, status, ordered_at, updated_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
       ON CONFLICT (order_id) DO UPDATE SET
         status = EXCLUDED.status,
         total_cents = EXCLUDED.total_cents,
         updated_at = NOW()`,
      [
        row.id,
        row.event_id,
        eventInfo?.name || 'Unknown',
        eventInfo?.venueCity || 'Unknown',
        row.user_id,
        userInfo?.email || 'Unknown',
        row.ticket_type,
        row.quantity,
        row.total_in_cents,
        row.status,
        row.created_at,
      ]
    );
  }

  private async handleEventChange(change: DebeziumChange): Promise<void> {
    if (change.op === 'd') return;
    const row = change.after;
    // Update cache for future order denormalization
    eventCache.set(row.id, { name: row.name, venueCity: row.venue_city || 'Unknown' });
    // Also update any existing order_facts that reference this event
    await analyticsDb.query(
      'UPDATE order_facts SET event_name = $1, venue_city = $2 WHERE event_id = $3',
      [row.name, row.venue_city || 'Unknown', row.id]
    );
  }

  private async handleUserChange(change: DebeziumChange): Promise<void> {
    if (change.op === 'd') return;
    const row = change.after;
    userCache.set(row.id, { email: row.email });
  }

  private async getEventInfo(eventId: string): Promise<{ name: string; venueCity: string } | undefined> {
    if (eventCache.has(eventId)) return eventCache.get(eventId);
    // Fallback: query the analytics DB (might have been populated by an earlier CDC message)
    const result = await analyticsDb.query(
      'SELECT DISTINCT event_name as name, venue_city FROM order_facts WHERE event_id = $1 LIMIT 1',
      [eventId]
    );
    if (result.rows.length > 0) {
      const info = { name: result.rows[0].name, venueCity: result.rows[0].venue_city };
      eventCache.set(eventId, info);
      return info;
    }
    return undefined;
  }

  private async getUserInfo(userId: string): Promise<{ email: string } | undefined> {
    return userCache.get(userId);
  }
}

interface DebeziumChange {
  op: 'c' | 'u' | 'd' | 'r';
  before: any;
  after: any;
  source: { table: string; ts_ms: number };
}
```

Start the consumer:

```typescript
// src/analytics/start-consumer.ts

import { CdcConsumer } from './cdc-consumer';

async function main() {
  const consumer = new CdcConsumer();
  await consumer.start();
  console.log('[analytics] CDC consumer is running');
}

main().catch(console.error);
```

```bash
npx ts-node src/analytics/start-consumer.ts
```

---

## 3. Try It: Watch Changes Flow (5 minutes)

Create an order in TicketPulse and watch it appear in the analytics database:

```bash
# Terminal 1: CDC consumer is running (from previous step)

# Terminal 2: Create an order via the TicketPulse API
curl -X POST http://localhost:3000/api/orders \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{
    "eventId": "evt_1",
    "ticketType": "general",
    "quantity": 2
  }'

# Terminal 3: Query the analytics database
psql -h localhost -p 5433 -U analytics -d ticketpulse_analytics \
  -c "SELECT order_id, event_name, ticket_type, quantity, total_cents, status FROM order_facts ORDER BY ordered_at DESC LIMIT 5;"
```

The order should appear in the analytics database within seconds. No application code was modified -- Debezium read it from the WAL.

---

## 4. Batch vs Stream: When to Use Each (5 minutes)

| Approach | Latency | Complexity | Best For |
|---|---|---|---|
| **CDC (streaming)** | Seconds | High (Kafka, Debezium, consumers) | Real-time dashboards, live availability |
| **Batch ETL** | Hours | Lower (a cron job + SQL queries) | Daily reports, monthly billing, ML training data |
| **Hybrid** | Both | Highest | Real-time for hot data, batch for historical backfills |

For TicketPulse:
- **Streaming** for: ticket availability (must be near real-time), live sales dashboard during a ticket rush
- **Batch** for: daily revenue reports, user cohort analysis, monthly partner settlements

> **Your decision:** The daily revenue materialized view -- should it be refreshed by the CDC stream or by a cron job?
>
> The stream approach: refresh after every order change event. Always up-to-date but adds load.
> The batch approach: refresh once per hour via `REFRESH MATERIALIZED VIEW CONCURRENTLY`. Good enough for a dashboard that does not need second-level precision.
>
> For a daily revenue report, batch is sufficient.

---

## 5. Observe: CDC Lag (5 minutes)

How quickly do changes propagate? Measure it:

```typescript
// src/analytics/lag-monitor.ts

import { Kafka } from 'kafkajs';

const admin = kafka.admin();

async function checkLag() {
  await admin.connect();

  const offsets = await admin.fetchOffsets({
    groupId: 'analytics-consumer',
    topics: ['ticketpulse.public.orders'],
  });

  const topicOffsets = await admin.fetchTopicOffsets('ticketpulse.public.orders');

  for (const partition of offsets) {
    const latest = topicOffsets.find(t => t.partition === partition.partition);
    const lag = Number(latest?.offset || 0) - Number(partition.offset);
    console.log(`Partition ${partition.partition}: offset=${partition.offset}, latest=${latest?.offset}, lag=${lag}`);
  }

  await admin.disconnect();
}

setInterval(checkLag, 5000);
```

Expose lag as a Prometheus metric:

```
Grafana panel:
  Query: kafka_consumer_group_lag{group="analytics-consumer",topic="ticketpulse.public.orders"}
  Alert: if lag > 1000 for 5 minutes → "Analytics pipeline is falling behind"
```

---

## 6. Build: Refresh the Daily Revenue View (5 minutes)

Set up a cron job to refresh the materialized view:

```typescript
// src/analytics/refresh-views.ts

import { Pool } from 'pg';

const analyticsDb = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'ticketpulse_analytics',
  user: 'analytics',
  password: 'analytics_pass',
});

async function refreshViews() {
  console.log('[views] Refreshing daily_revenue...');
  const start = Date.now();
  await analyticsDb.query('REFRESH MATERIALIZED VIEW CONCURRENTLY daily_revenue');
  console.log(`[views] daily_revenue refreshed in ${Date.now() - start}ms`);
}

refreshViews()
  .then(() => process.exit(0))
  .catch(err => {
    console.error('[views] Refresh failed:', err);
    process.exit(1);
  });
```

Schedule it:

```yaml
# Kubernetes CronJob
apiVersion: batch/v1
kind: CronJob
metadata:
  name: refresh-analytics-views
spec:
  schedule: "0 * * * *"  # Every hour
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: refresh
            image: ticketpulse/analytics:latest
            command: ["node", "dist/analytics/refresh-views.js"]
          restartPolicy: OnFailure
```

Query the view:

```sql
SELECT * FROM daily_revenue ORDER BY day DESC LIMIT 7;

-- Result:
--     day     | order_count | tickets_sold | revenue_cents | unique_buyers | events_with_sales
-- 2026-03-24  |    1,247    |    3,891     |  19,455,000   |     982       |        34
-- 2026-03-23  |    1,102    |    3,456     |  17,280,000   |     876       |        31
-- ...
```

---

## Checkpoint

Before continuing, verify:

- [ ] Debezium connector is running and reading from Postgres WAL
- [ ] Kafka topics exist for each captured table
- [ ] CDC consumer processes INSERT, UPDATE, DELETE events
- [ ] Order facts are denormalized (event name, venue city joined in)
- [ ] Materialized view `daily_revenue` returns correct aggregations
- [ ] Consumer lag is visible and monitored

```bash
git add -A && git commit -m "feat: add CDC pipeline with Debezium, Kafka consumer, and analytics DB"
```

---

## Reflect

LinkedIn built Kafka specifically for this use case -- change data capture across their data infrastructure. Before Kafka, teams at LinkedIn had dozens of point-to-point data pipelines, each with its own format, retry logic, and failure modes. Kafka gave them a single, ordered, replayable log that every consumer could read independently.

The same principle applies at TicketPulse's scale. Without CDC, adding analytics means: modify the application to publish events (code changes in every service), or run queries against production (performance risk), or set up database replication (schema-coupled). With CDC, the database itself becomes the event source. No application changes needed.

---

## Key Terms

| Term | Definition |
|------|-----------|
| **CDC** | Change Data Capture; a technique that detects and propagates data changes from a database to downstream consumers. |
| **Debezium** | An open-source CDC platform that streams database changes into event systems like Kafka. |
| **Data pipeline** | An automated sequence of steps that moves and transforms data from source systems to a destination. |
| **ETL** | Extract, Transform, Load; a traditional data integration pattern that moves data between systems. |
| **Stream processing** | The continuous, real-time processing of data records as they arrive, rather than in batches. |
| **Connector** | A component that integrates an external system (database, API, file) with a data pipeline or event platform. |

---

## What's Next

In **Feature Flags** (L2-M53), you'll ship code to production without releasing it to users — and control rollouts with fine-grained targeting.

---

## Further Reading

- "Designing Data-Intensive Applications" by Martin Kleppmann, Chapter 11 -- the definitive chapter on stream processing and derived data
- Debezium documentation -- comprehensive guides for Postgres, MySQL, MongoDB connectors
- "The Log: What every software engineer should know about real-time data's unifying abstraction" by Jay Kreps -- the LinkedIn blog post that explains why Kafka exists
- ClickHouse documentation -- if your analytics needs outgrow Postgres
