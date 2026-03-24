# L2-M51: CQRS in Practice

> **Loop 2 (Applied)** | Section 2D: Advanced Patterns | Duration: 75 min | Tier: Deep Dive
>
> **Prerequisites:** L2-M39 (Kubernetes Basics), L2-M44 (Kafka Basics or equivalent message broker familiarity)
>
> **What you'll build:** You will separate TicketPulse's read and write paths for the events feature -- a normalized write model in Postgres, an event-driven projection pipeline via Kafka, a denormalized read model optimized for display, and a "read-your-writes" consistency strategy.

---

## The Goal

TicketPulse's events page is slow. The query JOINs events with venues, pricing tiers, ticket availability, and organizer details. It takes 15ms on a warm cache, 80ms on a cold one. Meanwhile, the write path for creating events needs to enforce invariants: validate the venue capacity, check for scheduling conflicts, set up pricing tiers. These two operations have fundamentally different requirements, but they share the same data model and the same database.

CQRS (Command Query Responsibility Segregation) separates them. Writes go through a model optimized for correctness. Reads go through a model optimized for speed. The two models are synchronized via events.

**This module is a deep dive. CQRS adds significant complexity. You will build it, measure the performance gain, and then discuss when it is -- and is not -- worth the cost.**

---

## 0. The Current State (5 minutes)

Here is what the events query looks like today:

```sql
-- Current query: event detail page
-- 4 JOINs, filtering, aggregation
SELECT
  e.id, e.name, e.description, e.starts_at, e.ends_at, e.status,
  v.name AS venue_name, v.city, v.capacity,
  o.display_name AS organizer_name,
  json_agg(json_build_object(
    'tier', pt.name,
    'price_cents', pt.price_cents,
    'available', pt.capacity - COALESCE(sold.count, 0)
  )) AS pricing
FROM events e
JOIN venues v ON e.venue_id = v.id
JOIN organizers o ON e.organizer_id = o.id
JOIN pricing_tiers pt ON pt.event_id = e.id
LEFT JOIN (
  SELECT ticket_tier_id, COUNT(*) as count
  FROM tickets WHERE status = 'sold'
  GROUP BY ticket_tier_id
) sold ON sold.ticket_tier_id = pt.id
WHERE e.id = $1
GROUP BY e.id, v.id, o.id;
```

Run it and measure:

```bash
# With EXPLAIN ANALYZE
psql -d ticketpulse -c "EXPLAIN ANALYZE
  SELECT e.id, e.name, ...
  FROM events e
  JOIN venues v ON e.venue_id = v.id
  ...
  WHERE e.id = 'evt_popular_concert'
  GROUP BY e.id, v.id, o.id;"
```

Note the execution time. This is the baseline we want to beat.

---

## 1. Design: Separate Read and Write Models (10 minutes)

### Write Model (Command Side)

The write model stays normalized. It enforces business rules:

```
events (id, name, description, venue_id, organizer_id, starts_at, ends_at, status, created_at)
venues (id, name, address, city, capacity)
organizers (id, user_id, display_name, verified)
pricing_tiers (id, event_id, name, price_cents, capacity)
tickets (id, event_id, tier_id, order_id, status)
```

Commands that go through the write model:
- `CreateEvent` -- validates venue availability, creates event + pricing tiers
- `UpdateEvent` -- checks status transitions (draft → published, published → cancelled)
- `PurchaseTicket` -- enforces capacity, updates availability

### Read Model (Query Side)

The read model is denormalized and pre-computed. No JOINs at query time:

```sql
-- Read model: one table, one query, one index scan
CREATE TABLE event_read_model (
  event_id        TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  description     TEXT,
  starts_at       TIMESTAMPTZ NOT NULL,
  ends_at         TIMESTAMPTZ,
  status          TEXT NOT NULL,
  venue_name      TEXT NOT NULL,
  venue_city      TEXT NOT NULL,
  venue_capacity  INTEGER NOT NULL,
  organizer_name  TEXT NOT NULL,
  pricing         JSONB NOT NULL,       -- pre-computed pricing with availability
  total_available INTEGER NOT NULL,     -- pre-computed total tickets remaining
  search_text     TEXT NOT NULL,        -- pre-computed search field
  updated_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_event_read_status ON event_read_model(status);
CREATE INDEX idx_event_read_city ON event_read_model(venue_city);
CREATE INDEX idx_event_read_starts ON event_read_model(starts_at);
CREATE INDEX idx_event_read_search ON event_read_model USING gin(to_tsvector('english', search_text));
```

Query time: a single index scan on one table. No JOINs, no aggregation, no subqueries.

> **Your decision:** Should the read model live in the same Postgres instance or a separate one?
>
> - **Same instance:** Simpler ops, no network hop, good enough for most teams
> - **Separate instance:** Independent scaling, read replicas, can use a different store (Elasticsearch for search, Redis for hot data)
>
> Start with the same instance. Separate when you have evidence that read load is impacting write performance.

---

## 2. Build: The Write Side (15 minutes)

The command handler validates, writes to the normalized model, and publishes an event:

```typescript
// src/commands/create-event.handler.ts

import { Pool } from 'pg';
import { KafkaProducer } from '../messaging/kafka-producer';

interface CreateEventCommand {
  name: string;
  description: string;
  venueId: string;
  organizerId: string;
  startsAt: Date;
  endsAt: Date;
  pricingTiers: Array<{ name: string; priceCents: number; capacity: number }>;
}

export class CreateEventHandler {
  constructor(
    private db: Pool,
    private kafka: KafkaProducer
  ) {}

  async execute(command: CreateEventCommand): Promise<string> {
    const client = await this.db.connect();

    try {
      await client.query('BEGIN');

      // Validate: does the venue exist and have enough capacity?
      const venue = await client.query(
        'SELECT id, name, city, capacity FROM venues WHERE id = $1',
        [command.venueId]
      );
      if (venue.rows.length === 0) throw new Error('Venue not found');

      const totalTierCapacity = command.pricingTiers.reduce((sum, t) => sum + t.capacity, 0);
      if (totalTierCapacity > venue.rows[0].capacity) {
        throw new Error(`Total tier capacity (${totalTierCapacity}) exceeds venue capacity (${venue.rows[0].capacity})`);
      }

      // Validate: no scheduling conflict at this venue
      const conflict = await client.query(
        `SELECT id FROM events
         WHERE venue_id = $1 AND status != 'cancelled'
         AND starts_at < $3 AND ends_at > $2`,
        [command.venueId, command.startsAt, command.endsAt]
      );
      if (conflict.rows.length > 0) {
        throw new Error('Venue has a scheduling conflict');
      }

      // Write the event
      const eventResult = await client.query(
        `INSERT INTO events (name, description, venue_id, organizer_id, starts_at, ends_at, status)
         VALUES ($1, $2, $3, $4, $5, $6, 'draft')
         RETURNING id`,
        [command.name, command.description, command.venueId, command.organizerId, command.startsAt, command.endsAt]
      );
      const eventId = eventResult.rows[0].id;

      // Write pricing tiers
      for (const tier of command.pricingTiers) {
        await client.query(
          `INSERT INTO pricing_tiers (event_id, name, price_cents, capacity)
           VALUES ($1, $2, $3, $4)`,
          [eventId, tier.name, tier.priceCents, tier.capacity]
        );
      }

      // Fetch organizer name for the event payload
      const organizer = await client.query(
        'SELECT display_name FROM organizers WHERE id = $1',
        [command.organizerId]
      );

      await client.query('COMMIT');

      // Publish event AFTER commit succeeds
      // --- YOUR DECISION POINT ---
      // What if the Kafka publish fails after the DB commit?
      // Option A: Accept the inconsistency, rely on a periodic reconciliation job
      // Option B: Use the Outbox pattern (write the event to a DB table, a separate process publishes it)
      // Option C: Use a transactional outbox (write event in the same transaction)
      //
      // For now, use Option A. The Outbox pattern is covered in the further reading.

      await this.kafka.publish('events', {
        type: 'EventCreated',
        eventId,
        data: {
          name: command.name,
          description: command.description,
          startsAt: command.startsAt,
          endsAt: command.endsAt,
          status: 'draft',
          venue: {
            name: venue.rows[0].name,
            city: venue.rows[0].city,
            capacity: venue.rows[0].capacity,
          },
          organizer: {
            name: organizer.rows[0].display_name,
          },
          pricingTiers: command.pricingTiers.map(t => ({
            name: t.name,
            priceCents: t.priceCents,
            available: t.capacity,
          })),
        },
        timestamp: new Date().toISOString(),
      });

      return eventId;
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }
}
```

---

## 3. Build: The Read Side (15 minutes)

A consumer listens to the Kafka topic and updates the read model:

```typescript
// src/projections/event-read-model.projector.ts

import { Pool } from 'pg';
import { KafkaConsumer, KafkaMessage } from '../messaging/kafka-consumer';

export class EventReadModelProjector {
  constructor(
    private db: Pool,
    private consumer: KafkaConsumer
  ) {}

  async start(): Promise<void> {
    await this.consumer.subscribe('events', async (message: KafkaMessage) => {
      console.log(`[projector] Processing ${message.type} for event ${message.eventId}`);

      switch (message.type) {
        case 'EventCreated':
          await this.handleEventCreated(message);
          break;
        case 'EventUpdated':
          await this.handleEventUpdated(message);
          break;
        case 'TicketPurchased':
          await this.handleTicketPurchased(message);
          break;
        case 'EventCancelled':
          await this.handleEventCancelled(message);
          break;
        default:
          console.log(`[projector] Unknown event type: ${message.type}`);
      }
    });
  }

  private async handleEventCreated(message: KafkaMessage): Promise<void> {
    const { data } = message;
    const totalAvailable = data.pricingTiers.reduce(
      (sum: number, t: any) => sum + t.available, 0
    );
    const searchText = `${data.name} ${data.venue.name} ${data.venue.city} ${data.organizer.name}`;

    await this.db.query(
      `INSERT INTO event_read_model
        (event_id, name, description, starts_at, ends_at, status,
         venue_name, venue_city, venue_capacity, organizer_name,
         pricing, total_available, search_text, updated_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())
       ON CONFLICT (event_id) DO UPDATE SET
         name = EXCLUDED.name,
         description = EXCLUDED.description,
         starts_at = EXCLUDED.starts_at,
         ends_at = EXCLUDED.ends_at,
         status = EXCLUDED.status,
         venue_name = EXCLUDED.venue_name,
         venue_city = EXCLUDED.venue_city,
         venue_capacity = EXCLUDED.venue_capacity,
         organizer_name = EXCLUDED.organizer_name,
         pricing = EXCLUDED.pricing,
         total_available = EXCLUDED.total_available,
         search_text = EXCLUDED.search_text,
         updated_at = NOW()`,
      [
        message.eventId,
        data.name,
        data.description,
        data.startsAt,
        data.endsAt,
        data.status,
        data.venue.name,
        data.venue.city,
        data.venue.capacity,
        data.organizer.name,
        JSON.stringify(data.pricingTiers),
        totalAvailable,
        searchText,
      ]
    );
    console.log(`[projector] Read model updated for event ${message.eventId}`);
  }

  private async handleTicketPurchased(message: KafkaMessage): Promise<void> {
    const { data } = message;
    // Decrement availability in the denormalized pricing JSONB
    // and update total_available
    await this.db.query(
      `UPDATE event_read_model
       SET total_available = total_available - $2,
           pricing = (
             SELECT jsonb_agg(
               CASE
                 WHEN elem->>'name' = $3
                 THEN jsonb_set(elem, '{available}', to_jsonb((elem->>'available')::int - $2))
                 ELSE elem
               END
             )
             FROM jsonb_array_elements(pricing) elem
           ),
           updated_at = NOW()
       WHERE event_id = $1`,
      [message.eventId, data.quantity, data.tierName]
    );
  }

  private async handleEventUpdated(message: KafkaMessage): Promise<void> {
    const { data } = message;
    await this.db.query(
      `UPDATE event_read_model
       SET name = COALESCE($2, name),
           description = COALESCE($3, description),
           status = COALESCE($4, status),
           updated_at = NOW()
       WHERE event_id = $1`,
      [message.eventId, data.name, data.description, data.status]
    );
  }

  private async handleEventCancelled(message: KafkaMessage): Promise<void> {
    await this.db.query(
      `UPDATE event_read_model SET status = 'cancelled', updated_at = NOW() WHERE event_id = $1`,
      [message.eventId]
    );
  }
}
```

The query endpoint now reads from the flat table:

```typescript
// src/queries/get-event.handler.ts

import { Pool } from 'pg';

export class GetEventHandler {
  constructor(private readDb: Pool) {}

  async execute(eventId: string): Promise<EventReadModel | null> {
    const result = await this.readDb.query(
      'SELECT * FROM event_read_model WHERE event_id = $1',
      [eventId]
    );
    return result.rows[0] || null;
  }

  async search(query: string, city?: string): Promise<EventReadModel[]> {
    let sql = `SELECT * FROM event_read_model WHERE status = 'published'`;
    const params: any[] = [];

    if (query) {
      params.push(query);
      sql += ` AND to_tsvector('english', search_text) @@ plainto_tsquery('english', $${params.length})`;
    }
    if (city) {
      params.push(city);
      sql += ` AND venue_city = $${params.length}`;
    }

    sql += ' ORDER BY starts_at ASC LIMIT 50';
    const result = await this.readDb.query(sql, params);
    return result.rows;
  }
}
```

---

## 4. Try It: See the Consistency Lag (5 minutes)

```bash
# Create an event via the write path
curl -X POST http://localhost:3000/api/events \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "CQRS Demo Concert",
    "description": "Testing CQRS",
    "venueId": "venue_1",
    "organizerId": "org_1",
    "startsAt": "2026-06-01T20:00:00Z",
    "endsAt": "2026-06-01T23:00:00Z",
    "pricingTiers": [
      { "name": "General", "priceCents": 5000, "capacity": 500 },
      { "name": "VIP", "priceCents": 15000, "capacity": 50 }
    ]
  }'

# Immediately query the read model
curl http://localhost:3000/api/events/<event_id>
```

Depending on Kafka consumer lag, the read model might not have the event yet. This is eventual consistency in action.

---

## 5. Observe: Measure the Performance Gain (5 minutes)

```bash
# Query via the old path (JOINs):
psql -d ticketpulse -c "EXPLAIN ANALYZE SELECT ... FROM events e JOIN venues v ... WHERE e.id = 'evt_1'"
# Result: ~15ms, 4 table scans, hash joins

# Query via the read model:
psql -d ticketpulse -c "EXPLAIN ANALYZE SELECT * FROM event_read_model WHERE event_id = 'evt_1'"
# Result: ~0.5ms, 1 index scan, no joins
```

The read model is 30x faster. For a listing page that displays 50 events, the difference is 750ms vs 25ms. On a mobile connection, this is the difference between a usable app and an abandoned one.

---

## 6. Handle Eventual Consistency: Read-Your-Writes (10 minutes)

The classic problem: a user creates an event and immediately navigates to "My Events." The read model has not caught up yet. The event is missing. The user thinks it was lost.

```typescript
// src/queries/get-my-events.handler.ts

export class GetMyEventsHandler {
  constructor(
    private readDb: Pool,
    private writeDb: Pool
  ) {}

  async execute(
    organizerId: string,
    recentWriteIds?: string[]  // IDs the user just wrote (passed via session/cookie)
  ): Promise<EventReadModel[]> {
    // Get events from the read model
    const readResult = await this.readDb.query(
      `SELECT * FROM event_read_model
       WHERE organizer_name = (SELECT display_name FROM organizers WHERE id = $1)
       ORDER BY starts_at ASC`,
      [organizerId]
    );
    const readEvents = readResult.rows;

    if (!recentWriteIds || recentWriteIds.length === 0) {
      return readEvents;
    }

    // Check: are the recently written events in the read model?
    const readEventIds = new Set(readEvents.map(e => e.event_id));
    const missingIds = recentWriteIds.filter(id => !readEventIds.has(id));

    if (missingIds.length === 0) {
      return readEvents; // Read model is caught up
    }

    // Fallback: fetch missing events from the write model
    console.log(`[read-your-writes] ${missingIds.length} events not yet in read model, falling back to write DB`);

    const writeResult = await this.writeDb.query(
      `SELECT e.id as event_id, e.name, e.description, e.starts_at, e.ends_at, e.status,
              v.name as venue_name, v.city as venue_city, v.capacity as venue_capacity,
              o.display_name as organizer_name
       FROM events e
       JOIN venues v ON e.venue_id = v.id
       JOIN organizers o ON e.organizer_id = o.id
       WHERE e.id = ANY($1)`,
      [missingIds]
    );

    // Merge the two result sets
    const merged = [...readEvents, ...writeResult.rows];
    merged.sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime());
    return merged;
  }
}
```

The caller passes `recentWriteIds` from the session:

```typescript
// src/routes/events.routes.ts (excerpt)

app.post('/api/events', async (req, res) => {
  const eventId = await createEventHandler.execute(req.body);

  // Track the write in the session for read-your-writes
  if (!req.session.recentEventIds) req.session.recentEventIds = [];
  req.session.recentEventIds.push(eventId);

  // Clean up old IDs (older than 30 seconds -- read model should catch up by then)
  req.session.recentEventIds = req.session.recentEventIds.filter(
    (id: string, idx: number) => idx > req.session.recentEventIds.length - 10
  );

  res.status(201).json({ eventId });
});

app.get('/api/my-events', async (req, res) => {
  const events = await getMyEventsHandler.execute(
    req.user.organizerId,
    req.session.recentEventIds
  );
  res.json(events);
});
```

---

## 7. Common Mistake: CQRS Everywhere (5 minutes)

CQRS adds:
- A message broker (Kafka) and its operational overhead
- A projection process that must be monitored, restarted on failure, and replayed when schema changes
- Eventual consistency that complicates every user-facing flow
- Two data models to maintain instead of one

For TicketPulse's "user profile" page -- a simple `SELECT * FROM users WHERE id = $1` -- CQRS is absurd overhead. The query is fast, the model is simple, and there is no read/write asymmetry.

**Use CQRS when:**
- Read and write patterns are fundamentally different (many reads, few writes, or vice versa)
- The read query involves expensive JOINs or aggregations that can be pre-computed
- Read and write workloads need to scale independently
- You already have a message broker in your architecture

**Skip CQRS when:**
- Simple CRUD with no performance issues
- The domain is straightforward (no complex invariants on writes)
- Your team is small and operational overhead matters more than performance

---

## Checkpoint

Before continuing, verify:

- [ ] Write model: normalized tables with invariant enforcement
- [ ] Events published to Kafka on successful writes
- [ ] Projector consumes events and maintains the read model
- [ ] Read queries hit the denormalized table (no JOINs)
- [ ] Read model is 10x+ faster than the original query
- [ ] Read-your-writes fallback handles the consistency lag

```bash
git add -A && git commit -m "feat: implement CQRS for events with Kafka projections and read-your-writes"
```

---

## Reflect

CQRS is a trade-off. You traded simplicity (one model, one database, one query path) for performance and scalability (two models, a message broker, eventual consistency, a projection process). For TicketPulse's event listing -- a hot path that serves millions of reads per day with expensive JOINs -- the trade-off is worth it. For most other features, it is not.

The meta-lesson: **always start simple**. Add CQRS when you have measured evidence that the read path is a bottleneck. Never add it "just in case."

---

## Further Reading

- Martin Fowler, "CQRS" -- the canonical description of the pattern
- Greg Young, "CQRS Documents" -- the original paper that popularized event sourcing + CQRS
- "Designing Data-Intensive Applications" by Martin Kleppmann, Chapter 11 -- stream processing and derived data
- The Outbox Pattern -- a reliable way to publish events after a database commit (search for "Debezium Outbox" for a production-ready implementation)
