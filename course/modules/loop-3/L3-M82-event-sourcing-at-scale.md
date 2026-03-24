# L3-M82: Event Sourcing at Scale

> ⏱️ 75 min | 🔴 Expert | Prerequisites: L2-M34, L3-M81
> Source: Chapter 10 (Event Sourcing), Chapter 1 (CQRS/Event Sourcing theory)

## What You'll Learn

- Event sourcing as an alternative to traditional CRUD: store what happened, not what is
- Building an event-sourced order system for TicketPulse with an append-only event store
- Rebuilding current state by replaying events from the beginning
- Projections: building read-optimized views from events for different query needs
- Snapshots: an optimization that avoids replaying thousands of events
- Schema evolution: handling events whose shape changes over time
- GDPR compliance with crypto-shredding: encrypting PII per user, deleting the key to "forget" them

## Why This Matters

TicketPulse's order table has a `status` column: `pending`, `confirmed`, `cancelled`, `refunded`. When a customer calls support and says "I bought two tickets but only got one," the support agent looks at the order and sees `status: confirmed`. But what happened between creation and confirmation? Was a third ticket originally in the order and then removed? Was the payment retried? When exactly did each state change happen?

With traditional CRUD, the answers are gone. Each `UPDATE orders SET status = 'confirmed'` overwrites the previous state. The database stores the latest truth, not the history.

Event sourcing inverts this. Instead of storing current state, you store the sequence of events that led to the current state. Every change is an immutable fact appended to a log. The current state is derived by replaying those events. You never lose information. You can answer "what was the state at 3:47 PM?" or "what sequence of changes led to this refund?" by reading the event log.

This is how bank ledgers work. This is how Git works. This is how Kafka works internally. And for domains where auditability, temporal queries, and complete history matter -- like orders, payments, and compliance -- event sourcing is the right model.

---

## 1. Events vs State: Two Ways of Thinking

### Traditional CRUD (State-Based)

```sql
-- The orders table stores current state
CREATE TABLE orders (
  id          UUID PRIMARY KEY,
  user_id     UUID NOT NULL,
  event_id    UUID NOT NULL,
  status      VARCHAR(20) NOT NULL, -- 'pending', 'confirmed', 'cancelled', 'refunded'
  total_amount INTEGER NOT NULL,
  seats       JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL,
  updated_at  TIMESTAMPTZ NOT NULL
);

-- To confirm an order:
UPDATE orders SET status = 'confirmed', updated_at = NOW() WHERE id = $1;
-- The fact that it was ever 'pending' is gone.
```

### Event Sourcing (Event-Based)

```sql
-- The event store records what happened
CREATE TABLE events (
  id            BIGSERIAL PRIMARY KEY,
  aggregate_id  UUID NOT NULL,         -- The order ID
  aggregate_type VARCHAR(50) NOT NULL,  -- 'Order'
  event_type    VARCHAR(100) NOT NULL,  -- 'OrderCreated', 'PaymentReceived', etc.
  data          JSONB NOT NULL,         -- Event payload
  metadata      JSONB DEFAULT '{}',     -- Causation ID, correlation ID, user agent
  version       INTEGER NOT NULL,       -- Optimistic concurrency control
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(aggregate_id, version)         -- No two events for same aggregate at same version
);

-- Index for loading an aggregate's events
CREATE INDEX idx_events_aggregate ON events (aggregate_id, version);
```

The event store is **append-only**. You never UPDATE or DELETE rows. Every row is an immutable fact about something that happened.

---

## 2. Build: Event-Sourced Orders for TicketPulse

### Define the Events

Events are named in past tense -- they describe things that already happened:

```typescript
// events/order-events.ts

interface OrderCreated {
  type: 'OrderCreated';
  orderId: string;
  userId: string;
  eventId: string;
  seats: string[];
  totalAmount: number;
  currency: string;
  createdAt: string;
}

interface TicketAdded {
  type: 'TicketAdded';
  orderId: string;
  seatId: string;
  price: number;
}

interface TicketRemoved {
  type: 'TicketRemoved';
  orderId: string;
  seatId: string;
  reason: string;
}

interface PaymentReceived {
  type: 'PaymentReceived';
  orderId: string;
  paymentId: string;
  amount: number;
  method: string;
  processedAt: string;
}

interface OrderConfirmed {
  type: 'OrderConfirmed';
  orderId: string;
  confirmedAt: string;
}

interface OrderCancelled {
  type: 'OrderCancelled';
  orderId: string;
  reason: string;
  cancelledBy: string; // 'user' | 'system' | 'admin'
  cancelledAt: string;
}

interface RefundIssued {
  type: 'RefundIssued';
  orderId: string;
  refundId: string;
  amount: number;
  reason: string;
  issuedAt: string;
}

type OrderEvent =
  | OrderCreated
  | TicketAdded
  | TicketRemoved
  | PaymentReceived
  | OrderConfirmed
  | OrderCancelled
  | RefundIssued;
```

### The Event Store

```typescript
// event-store.ts
import { db } from '../database';

export class EventStore {
  async append(
    aggregateId: string,
    aggregateType: string,
    events: Array<{ type: string; data: any }>,
    expectedVersion: number
  ): Promise<void> {
    const client = await db.pool.connect();

    try {
      await client.query('BEGIN');

      // Optimistic concurrency: check the current version
      const { rows } = await client.query(
        `SELECT COALESCE(MAX(version), 0) as current_version
         FROM events WHERE aggregate_id = $1`,
        [aggregateId]
      );

      const currentVersion = rows[0].current_version;

      if (currentVersion !== expectedVersion) {
        throw new ConcurrencyError(
          `Expected version ${expectedVersion}, but found ${currentVersion}. ` +
          `Another process modified this aggregate.`
        );
      }

      // Append each event with incrementing versions
      for (let i = 0; i < events.length; i++) {
        const version = expectedVersion + i + 1;
        await client.query(
          `INSERT INTO events (aggregate_id, aggregate_type, event_type, data, version)
           VALUES ($1, $2, $3, $4, $5)`,
          [aggregateId, aggregateType, events[i].type, JSON.stringify(events[i].data), version]
        );
      }

      await client.query('COMMIT');
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  async getEvents(
    aggregateId: string,
    fromVersion: number = 0
  ): Promise<Array<{ type: string; data: any; version: number; createdAt: Date }>> {
    const { rows } = await db.query(
      `SELECT event_type as type, data, version, created_at
       FROM events
       WHERE aggregate_id = $1 AND version > $2
       ORDER BY version ASC`,
      [aggregateId, fromVersion]
    );

    return rows.map(row => ({
      type: row.type,
      data: typeof row.data === 'string' ? JSON.parse(row.data) : row.data,
      version: row.version,
      createdAt: row.created_at,
    }));
  }
}
```

### The Order Aggregate

The aggregate applies events to build current state:

```typescript
// aggregates/order.ts

interface OrderState {
  id: string;
  userId: string;
  eventId: string;
  seats: string[];
  totalAmount: number;
  currency: string;
  status: 'pending' | 'confirmed' | 'cancelled' | 'refunded';
  paymentId: string | null;
  version: number;
}

export class OrderAggregate {
  private state: OrderState;
  private pendingEvents: OrderEvent[] = [];

  constructor(private eventStore: EventStore) {
    this.state = this.initialState();
  }

  private initialState(): OrderState {
    return {
      id: '',
      userId: '',
      eventId: '',
      seats: [],
      totalAmount: 0,
      currency: 'USD',
      status: 'pending',
      paymentId: null,
      version: 0,
    };
  }

  // Load the aggregate by replaying its events
  async load(aggregateId: string): Promise<void> {
    const events = await this.eventStore.getEvents(aggregateId);

    for (const event of events) {
      this.apply(event);
      this.state.version = event.version;
    }
  }

  // Apply an event to the state (the "fold" function)
  private apply(event: { type: string; data: any }): void {
    switch (event.type) {
      case 'OrderCreated':
        this.state.id = event.data.orderId;
        this.state.userId = event.data.userId;
        this.state.eventId = event.data.eventId;
        this.state.seats = event.data.seats;
        this.state.totalAmount = event.data.totalAmount;
        this.state.currency = event.data.currency;
        this.state.status = 'pending';
        break;

      case 'TicketAdded':
        this.state.seats.push(event.data.seatId);
        this.state.totalAmount += event.data.price;
        break;

      case 'TicketRemoved':
        this.state.seats = this.state.seats.filter(s => s !== event.data.seatId);
        // Note: we'd need the price in a real system to adjust totalAmount
        break;

      case 'PaymentReceived':
        this.state.paymentId = event.data.paymentId;
        break;

      case 'OrderConfirmed':
        this.state.status = 'confirmed';
        break;

      case 'OrderCancelled':
        this.state.status = 'cancelled';
        break;

      case 'RefundIssued':
        this.state.status = 'refunded';
        break;
    }
  }

  // Commands: validate business rules, then emit events

  confirmOrder(): void {
    if (this.state.status !== 'pending') {
      throw new Error(`Cannot confirm order in status: ${this.state.status}`);
    }
    if (!this.state.paymentId) {
      throw new Error('Cannot confirm order without payment');
    }

    this.pendingEvents.push({
      type: 'OrderConfirmed',
      orderId: this.state.id,
      confirmedAt: new Date().toISOString(),
    });
  }

  cancelOrder(reason: string, cancelledBy: string): void {
    if (this.state.status === 'cancelled' || this.state.status === 'refunded') {
      throw new Error(`Cannot cancel order in status: ${this.state.status}`);
    }

    this.pendingEvents.push({
      type: 'OrderCancelled',
      orderId: this.state.id,
      reason,
      cancelledBy,
      cancelledAt: new Date().toISOString(),
    });
  }

  // Save pending events to the store
  async save(): Promise<void> {
    if (this.pendingEvents.length === 0) return;

    await this.eventStore.append(
      this.state.id,
      'Order',
      this.pendingEvents.map(e => ({ type: e.type, data: e })),
      this.state.version
    );

    // Apply events to local state
    for (const event of this.pendingEvents) {
      this.apply({ type: event.type, data: event });
      this.state.version++;
    }

    this.pendingEvents = [];
  }

  getState(): Readonly<OrderState> {
    return { ...this.state };
  }
}
```

### Using the Aggregate

```typescript
// Confirm an order
const order = new OrderAggregate(eventStore);
await order.load('ord_123');
order.confirmOrder();
await order.save();

// The event store now has a new event:
// { type: 'OrderConfirmed', data: { orderId: 'ord_123', confirmedAt: '...' }, version: 5 }
```

---

## 3. Projections: Read-Optimized Views from Events

Replaying events to rebuild state works for commands (writes), but it is too slow for queries. If an order has 20 events, replaying them for every `GET /orders/:id` request is wasteful.

**Projections** solve this by maintaining denormalized, read-optimized views that are updated as events are appended.

### Projection 1: Order Summary (for "My Orders" page)

```typescript
// projections/order-summary.ts

interface OrderSummaryView {
  orderId: string;
  userId: string;
  eventId: string;
  eventName: string;
  seatCount: number;
  totalAmount: number;
  status: string;
  createdAt: string;
  confirmedAt: string | null;
}

export class OrderSummaryProjection {
  async handle(event: { type: string; data: any }): Promise<void> {
    switch (event.type) {
      case 'OrderCreated':
        await db.query(
          `INSERT INTO order_summaries
           (order_id, user_id, event_id, seat_count, total_amount, status, created_at)
           VALUES ($1, $2, $3, $4, $5, 'pending', $6)`,
          [
            event.data.orderId,
            event.data.userId,
            event.data.eventId,
            event.data.seats.length,
            event.data.totalAmount,
            event.data.createdAt,
          ]
        );
        break;

      case 'OrderConfirmed':
        await db.query(
          `UPDATE order_summaries
           SET status = 'confirmed', confirmed_at = $2
           WHERE order_id = $1`,
          [event.data.orderId, event.data.confirmedAt]
        );
        break;

      case 'OrderCancelled':
        await db.query(
          `UPDATE order_summaries SET status = 'cancelled' WHERE order_id = $1`,
          [event.data.orderId]
        );
        break;

      case 'RefundIssued':
        await db.query(
          `UPDATE order_summaries SET status = 'refunded' WHERE order_id = $1`,
          [event.data.orderId]
        );
        break;
    }
  }
}
```

### Projection 2: Revenue Analytics (daily revenue by event)

```typescript
// projections/revenue-analytics.ts

export class RevenueAnalyticsProjection {
  async handle(event: { type: string; data: any; createdAt: Date }): Promise<void> {
    if (event.type !== 'PaymentReceived') return;

    const date = event.createdAt.toISOString().split('T')[0]; // YYYY-MM-DD

    await db.query(
      `INSERT INTO daily_revenue (date, event_id, total_revenue, order_count)
       VALUES ($1, $2, $3, 1)
       ON CONFLICT (date, event_id)
       DO UPDATE SET
         total_revenue = daily_revenue.total_revenue + $3,
         order_count = daily_revenue.order_count + 1`,
      [date, event.data.eventId, event.data.amount]
    );
  }
}
```

### Running Projections

Projections subscribe to the event stream and process events as they arrive:

```typescript
// projection-runner.ts

const projections = [
  new OrderSummaryProjection(),
  new RevenueAnalyticsProjection(),
];

// Process new events (poll-based, simple version)
async function runProjections(): Promise<void> {
  let lastProcessedId = await getLastProcessedEventId();

  while (true) {
    const { rows: events } = await db.query(
      `SELECT id, aggregate_id, event_type as type, data, created_at
       FROM events
       WHERE id > $1
       ORDER BY id ASC
       LIMIT 100`,
      [lastProcessedId]
    );

    for (const event of events) {
      for (const projection of projections) {
        await projection.handle(event);
      }
      lastProcessedId = event.id;
    }

    await saveLastProcessedEventId(lastProcessedId);

    if (events.length < 100) {
      // No more events — wait before polling again
      await sleep(100);
    }
  }
}
```

**Important**: Projections are eventually consistent. A write might not appear in a projection for a few milliseconds. This is acceptable for analytics and most read scenarios. If you need immediate consistency, read from the aggregate (replay events) for that specific query.

---

## 4. Snapshots: Performance Optimization

If an order has 1,000 events (think: a group order that has been modified many times), replaying all of them is slow. Snapshots solve this.

```typescript
// snapshots.ts

export class SnapshotStore {
  async save(
    aggregateId: string,
    state: any,
    version: number
  ): Promise<void> {
    await db.query(
      `INSERT INTO snapshots (aggregate_id, state, version, created_at)
       VALUES ($1, $2, $3, NOW())
       ON CONFLICT (aggregate_id)
       DO UPDATE SET state = $2, version = $3, created_at = NOW()`,
      [aggregateId, JSON.stringify(state), version]
    );
  }

  async load(aggregateId: string): Promise<{ state: any; version: number } | null> {
    const { rows } = await db.query(
      `SELECT state, version FROM snapshots WHERE aggregate_id = $1`,
      [aggregateId]
    );

    if (rows.length === 0) return null;

    return {
      state: JSON.parse(rows[0].state),
      version: rows[0].version,
    };
  }
}

// Modified aggregate loading with snapshot support
async function loadWithSnapshot(aggregateId: string): Promise<OrderAggregate> {
  const order = new OrderAggregate(eventStore);

  // Try loading from snapshot first
  const snapshot = await snapshotStore.load(aggregateId);

  if (snapshot) {
    // Start from snapshot state
    order.restoreFromSnapshot(snapshot.state, snapshot.version);

    // Only replay events AFTER the snapshot
    const recentEvents = await eventStore.getEvents(aggregateId, snapshot.version);
    for (const event of recentEvents) {
      order.applyEvent(event);
    }
  } else {
    // No snapshot — replay all events
    await order.load(aggregateId);
  }

  // Save a new snapshot if we replayed more than 100 events since last snapshot
  const eventsSinceSnapshot = snapshot
    ? order.getState().version - snapshot.version
    : order.getState().version;

  if (eventsSinceSnapshot > 100) {
    await snapshotStore.save(aggregateId, order.getState(), order.getState().version);
  }

  return order;
}
```

**Snapshot strategy**: Take a snapshot after every N events (e.g., 100). Loading becomes: load snapshot + replay only the events since the snapshot. For most aggregates, this means replaying 0-100 events instead of thousands.

---

## 5. Schema Evolution: When Events Change Shape

Events are immutable and stored forever. But your code evolves. What happens when you add a field to an event?

### The Problem

Version 1 of `OrderCreated` has no `currency` field:

```json
{ "type": "OrderCreated", "orderId": "ord_1", "totalAmount": 5000 }
```

Version 2 adds `currency`:

```json
{ "type": "OrderCreated", "orderId": "ord_2", "totalAmount": 5000, "currency": "USD" }
```

Old events do not have `currency`. Your aggregate code expects it. What do you do?

### Solution: Upcasting

Transform old events to the new shape when loading them:

```typescript
// upcasters.ts

const upcasters: Record<string, (data: any) => any> = {
  // OrderCreated v1 → v2: add default currency
  'OrderCreated': (data) => {
    if (!data.currency) {
      return { ...data, currency: 'USD' };
    }
    return data;
  },

  // TicketAdded v1 → v2: add tax field
  'TicketAdded': (data) => {
    if (data.tax === undefined) {
      return { ...data, tax: 0 };
    }
    return data;
  },
};

function upcastEvent(event: { type: string; data: any }): { type: string; data: any } {
  const upcaster = upcasters[event.type];
  if (upcaster) {
    return { ...event, data: upcaster(event.data) };
  }
  return event;
}
```

Upcasters are applied when events are loaded, not stored. The original event data in the database is never modified. This keeps the event store as a true source of truth.

---

## 6. GDPR + Event Sourcing: Crypto-Shredding

### The Problem

GDPR gives users the "right to be forgotten." But events are immutable -- you cannot delete them without breaking the event log. If `OrderCreated` contains `userId: "u_123"` and `email: "alice@example.com"`, how do you forget Alice?

### The Solution: Crypto-Shredding

Encrypt PII per user. When a user requests deletion, delete their encryption key. The events still exist, but the PII is now unreadable ciphertext.

```typescript
// crypto-shredding.ts
import { createCipheriv, createDecipheriv, randomBytes } from 'crypto';

class CryptoShredder {
  // Each user gets their own encryption key
  async getOrCreateKey(userId: string): Promise<Buffer> {
    const { rows } = await db.query(
      `SELECT encryption_key FROM user_keys WHERE user_id = $1`,
      [userId]
    );

    if (rows.length > 0) {
      return Buffer.from(rows[0].encryption_key, 'hex');
    }

    const key = randomBytes(32); // AES-256
    await db.query(
      `INSERT INTO user_keys (user_id, encryption_key) VALUES ($1, $2)`,
      [userId, key.toString('hex')]
    );

    return key;
  }

  // Encrypt PII before storing in event data
  encrypt(key: Buffer, plaintext: string): string {
    const iv = randomBytes(16);
    const cipher = createCipheriv('aes-256-cbc', key, iv);
    const encrypted = Buffer.concat([cipher.update(plaintext), cipher.final()]);
    return iv.toString('hex') + ':' + encrypted.toString('hex');
  }

  // Decrypt PII when reading events
  decrypt(key: Buffer, ciphertext: string): string {
    const [ivHex, encryptedHex] = ciphertext.split(':');
    const decipher = createDecipheriv(
      'aes-256-cbc', key, Buffer.from(ivHex, 'hex')
    );
    return Buffer.concat([
      decipher.update(Buffer.from(encryptedHex, 'hex')),
      decipher.final(),
    ]).toString();
  }

  // GDPR "forget" — delete the user's key
  async forgetUser(userId: string): Promise<void> {
    await db.query(`DELETE FROM user_keys WHERE user_id = $1`, [userId]);
    // Events still exist, but PII is now permanently unreadable.
    // Projections should be updated to remove/anonymize the user's data.
  }
}
```

When storing events, PII fields are encrypted:

```typescript
const key = await cryptoShredder.getOrCreateKey(userId);

const event = {
  type: 'OrderCreated',
  orderId: 'ord_123',
  userId: userId,                                           // Not PII (internal ID)
  email: cryptoShredder.encrypt(key, 'alice@example.com'),  // Encrypted PII
  name: cryptoShredder.encrypt(key, 'Alice Smith'),         // Encrypted PII
  eventId: 'evt_456',
  totalAmount: 5000,
};
```

After `forgetUser('u_123')`:
- The events still exist in the store (the event log is not broken)
- The `email` and `name` fields contain ciphertext that can never be decrypted
- Projections should be updated to show "Deleted User" or anonymized data

---

## 7. Reflect: When Is Event Sourcing Worth It?

### Stop and Think (10 minutes)

Event sourcing gives you a complete audit trail and temporal queries. But it adds significant complexity: projections, eventual consistency, schema evolution, crypto-shredding. For which TicketPulse domains is it worth it?

**Strong candidates:**
- **Orders/Payments**: Audit trail is legally required. Temporal queries answer support questions. Financial reconciliation needs immutable records.
- **Compliance/KYC**: Regulatory requirements for complete audit history of identity verification steps.

**Maybe:**
- **Event management**: Tracking how an event listing changed over time has some value, but is it worth the complexity?
- **User profiles**: History of profile changes is nice but probably overkill.

**Probably not:**
- **Session management**: Ephemeral by nature. No audit requirement.
- **Real-time seat availability**: Needs to be fast, not auditable. A simple counter is better.

The decision is not "event sourcing is better." It is "for this specific domain, does the value of complete history justify the cost of maintaining it?"

---

## Checkpoint: What You Built

You have:

- [x] Built an append-only event store with optimistic concurrency control
- [x] Implemented the Order aggregate that rebuilds state by replaying events
- [x] Created two projections: order summary (for the UI) and revenue analytics (for business)
- [x] Added snapshot support to avoid replaying thousands of events
- [x] Handled schema evolution with upcasters
- [x] Implemented GDPR compliance with crypto-shredding

**Key insight**: Event sourcing stores what happened, not what is. Current state is a derived view. This gives you a complete audit trail, temporal queries, and the ability to build new projections from historical data -- but at the cost of eventual consistency, schema evolution complexity, and the need for crypto-shredding for PII.

---

**Next module**: L3-M83 — Advanced Kubernetes, where we production-harden TicketPulse's K8s deployment with NetworkPolicies, RBAC, security contexts, and Pod Disruption Budgets.
