# L1-M16c: Design Patterns That Matter

> **Loop 1 (Foundation)** | Section 1D: Software Engineering Principles | Duration: 75 min | Tier: Deep Dive
>
> **Prerequisites:** L1-M16a (SOLID Principles in Practice), L1-M16b (Clean Code & Design Principles)
>
> **What you'll build:** Five design patterns applied to real TicketPulse features -- Strategy for pricing, Observer for event-driven side effects, Repository for data access, Decorator for logging and caching, and Factory for notification delivery.

---

## The Goal

Design patterns are not abstract theory. They are named solutions to problems that appear in every backend system. You have already seen some of them (Strategy in M16a, Repository hints in M16a's DIP refactoring). This module makes each pattern concrete by building it into TicketPulse.

The Gang of Four cataloged 23 patterns in 1994. You do not need all 23. These five cover 80% of what backend engineers encounter.

**You will run code within the first two minutes.**

---

## 0. Quick Start (2 minutes)

Set up the files for this module:

```bash
cd ticketpulse
mkdir -p src/patterns src/notifications
```

Create a shared types file:

```typescript
// src/patterns/types.ts

export interface Event {
  id: string;
  name: string;
  basePriceCents: number;
  category: 'concert' | 'conference' | 'sports' | 'theater';
  startsAt: Date;
}

export interface Order {
  id: string;
  eventId: string;
  userId: string;
  ticketType: string;
  quantity: number;
  totalInCents: number;
  status: string;
  createdAt: Date;
}

export interface User {
  id: string;
  email: string;
  phone: string | null;
  pushToken: string | null;
  notificationPreference: 'email' | 'sms' | 'push';
}
```

Verify:

```bash
npx tsc --noEmit src/patterns/types.ts
```

Good. Let us build five patterns.

---

## 1. Strategy Pattern: Ticket Pricing

**Problem:** TicketPulse has four ticket pricing models (flat, percentage discount, early bird, VIP surcharge). The pricing logic lives in a growing if/else chain. Every new pricing model requires editing the same function, risking regressions in existing models.

**Solution:** Define a `PricingStrategy` interface. Each pricing model is a separate class. The caller picks the strategy at runtime.

### Build: PricingStrategy Interface + 4 Implementations

```typescript
// src/patterns/pricing-strategy.ts

export interface PricingStrategy {
  readonly name: string;
  calculate(basePriceCents: number, quantity: number): number;
}

// Strategy 1: Standard flat pricing
export class FlatPricing implements PricingStrategy {
  readonly name = 'flat';

  calculate(basePriceCents: number, quantity: number): number {
    return basePriceCents * quantity;
  }
}

// Strategy 2: Percentage discount (e.g., 20% off for promotional events)
export class PercentageDiscountPricing implements PricingStrategy {
  readonly name = 'percentage_discount';

  constructor(private discountRate: number) {
    if (discountRate < 0 || discountRate > 1) {
      throw new Error('Discount rate must be between 0 and 1');
    }
  }

  calculate(basePriceCents: number, quantity: number): number {
    const discountedPrice = basePriceCents * (1 - this.discountRate);
    return Math.round(discountedPrice * quantity);
  }
}

// Strategy 3: Early bird -- discount for purchases made before a cutoff date
export class EarlyBirdPricing implements PricingStrategy {
  readonly name = 'early_bird';

  constructor(
    private discountRate: number,
    private cutoffDate: Date,
    private now: Date = new Date()
  ) {}

  calculate(basePriceCents: number, quantity: number): number {
    const isEarlyBird = this.now < this.cutoffDate;
    const rate = isEarlyBird ? (1 - this.discountRate) : 1;
    return Math.round(basePriceCents * rate * quantity);
  }
}

// Strategy 4: VIP surcharge -- premium seating at a markup
export class VipSurchargePricing implements PricingStrategy {
  readonly name = 'vip_surcharge';

  constructor(private surchargeMultiplier: number = 2.5) {}

  calculate(basePriceCents: number, quantity: number): number {
    return Math.round(basePriceCents * this.surchargeMultiplier * quantity);
  }
}
```

### Build: Inject Strategy Based on Event Type

```typescript
// src/patterns/pricing-context.ts

import {
  PricingStrategy,
  FlatPricing,
  PercentageDiscountPricing,
  EarlyBirdPricing,
  VipSurchargePricing,
} from './pricing-strategy';
import { Event } from './types';

export function getPricingStrategy(
  event: Event,
  ticketType: string,
  purchaseDate: Date = new Date()
): PricingStrategy {
  // VIP tickets always use surcharge pricing
  if (ticketType === 'vip') {
    return new VipSurchargePricing(2.5);
  }

  // Early bird pricing for tickets purchased 30+ days before event
  if (ticketType === 'early_bird') {
    const cutoff = new Date(event.startsAt);
    cutoff.setDate(cutoff.getDate() - 30);
    return new EarlyBirdPricing(0.2, cutoff, purchaseDate);
  }

  // Conference events get a 15% promotional discount
  if (event.category === 'conference') {
    return new PercentageDiscountPricing(0.15);
  }

  // Default: flat pricing
  return new FlatPricing();
}
```

### Test It

```typescript
// src/patterns/pricing-strategy.test.ts

import {
  FlatPricing,
  PercentageDiscountPricing,
  EarlyBirdPricing,
  VipSurchargePricing,
} from './pricing-strategy';

describe('PricingStrategy', () => {
  const BASE_PRICE = 10000; // $100.00

  describe('FlatPricing', () => {
    it('multiplies base price by quantity', () => {
      const strategy = new FlatPricing();
      expect(strategy.calculate(BASE_PRICE, 3)).toBe(30000);
    });
  });

  describe('PercentageDiscountPricing', () => {
    it('applies a percentage discount', () => {
      const strategy = new PercentageDiscountPricing(0.2); // 20% off
      expect(strategy.calculate(BASE_PRICE, 1)).toBe(8000); // $80
    });

    it('rejects invalid discount rates', () => {
      expect(() => new PercentageDiscountPricing(1.5)).toThrow();
      expect(() => new PercentageDiscountPricing(-0.1)).toThrow();
    });
  });

  describe('EarlyBirdPricing', () => {
    const eventDate = new Date('2026-06-01');
    const cutoff = new Date('2026-05-01'); // 30 days before

    it('applies discount when purchasing before cutoff', () => {
      const earlyPurchase = new Date('2026-04-15');
      const strategy = new EarlyBirdPricing(0.2, cutoff, earlyPurchase);
      expect(strategy.calculate(BASE_PRICE, 1)).toBe(8000);
    });

    it('charges full price when purchasing after cutoff', () => {
      const latePurchase = new Date('2026-05-15');
      const strategy = new EarlyBirdPricing(0.2, cutoff, latePurchase);
      expect(strategy.calculate(BASE_PRICE, 1)).toBe(10000);
    });
  });

  describe('VipSurchargePricing', () => {
    it('applies 2.5x surcharge', () => {
      const strategy = new VipSurchargePricing(2.5);
      expect(strategy.calculate(BASE_PRICE, 2)).toBe(50000); // 2 * $250
    });
  });
});
```

```bash
npx jest src/patterns/pricing-strategy.test.ts
```

**Why this matters:** Adding a fifth pricing model (say, "student" at 40% off) means creating one new class -- `StudentPricing`. Zero changes to existing strategies. Zero changes to the pricing context unless you need a new selection rule.

---

## 2. Observer / EventEmitter: TicketPurchased Side Effects

**Problem:** When a ticket is purchased, TicketPulse must send a confirmation email, update analytics, and decrement available inventory. Currently these are all inline in `createOrder()`. Adding a Slack notification means editing the purchase function.

**Solution:** Emit a `TicketPurchased` event. Listeners handle side effects independently. The purchase function does not know or care who is listening.

### Build: EventBus

```typescript
// src/patterns/event-bus.ts

export interface DomainEvent {
  type: string;
  timestamp: Date;
  payload: Record<string, unknown>;
}

export type EventHandler = (event: DomainEvent) => Promise<void>;

export class EventBus {
  private handlers = new Map<string, EventHandler[]>();

  on(eventType: string, handler: EventHandler): void {
    const existing = this.handlers.get(eventType) ?? [];
    existing.push(handler);
    this.handlers.set(eventType, existing);
  }

  off(eventType: string, handler: EventHandler): void {
    const existing = this.handlers.get(eventType) ?? [];
    this.handlers.set(
      eventType,
      existing.filter(h => h !== handler)
    );
  }

  async emit(event: DomainEvent): Promise<{ successes: number; failures: number }> {
    const handlers = this.handlers.get(event.type) ?? [];
    let successes = 0;
    let failures = 0;

    const results = await Promise.allSettled(
      handlers.map(handler => handler(event))
    );

    for (const result of results) {
      if (result.status === 'fulfilled') {
        successes++;
      } else {
        failures++;
        console.error(`Handler failed for ${event.type}:`, result.reason);
      }
    }

    return { successes, failures };
  }

  listenerCount(eventType: string): number {
    return (this.handlers.get(eventType) ?? []).length;
  }
}
```

### Build: Register Listeners

```typescript
// src/patterns/purchase-listeners.ts

import { DomainEvent, EventBus } from './event-bus';

// Listener 1: Send confirmation email
async function handleSendConfirmationEmail(event: DomainEvent): Promise<void> {
  const { orderId, userId, eventName, quantity, totalInCents } = event.payload as any;
  console.log(`[EMAIL] Sending confirmation to user ${userId} for order ${orderId}`);
  // In production: await emailService.sendOrderConfirmation(...)
}

// Listener 2: Update analytics
async function handleTrackPurchaseAnalytics(event: DomainEvent): Promise<void> {
  const { orderId, eventId, ticketType, quantity, totalInCents } = event.payload as any;
  console.log(JSON.stringify({
    metric: 'ticket_purchased',
    orderId,
    eventId,
    ticketType,
    quantity,
    revenue: totalInCents,
    timestamp: event.timestamp.toISOString(),
  }));
}

// Listener 3: Update inventory
async function handleUpdateInventory(event: DomainEvent): Promise<void> {
  const { eventId, quantity } = event.payload as any;
  console.log(`[INVENTORY] Reserving ${quantity} tickets for event ${eventId}`);
  // In production: await inventoryService.reserve(eventId, quantity)
}

// Listener 4: Easy to add later -- no changes to purchase logic
async function handleSlackNotification(event: DomainEvent): Promise<void> {
  const { orderId, totalInCents } = event.payload as any;
  console.log(`[SLACK] New sale: Order ${orderId} for $${(totalInCents as number / 100).toFixed(2)}`);
}

// Wire everything up
export function registerPurchaseListeners(eventBus: EventBus): void {
  eventBus.on('TicketPurchased', handleSendConfirmationEmail);
  eventBus.on('TicketPurchased', handleTrackPurchaseAnalytics);
  eventBus.on('TicketPurchased', handleUpdateInventory);
  eventBus.on('TicketPurchased', handleSlackNotification);
}
```

### Build: Emit From Purchase Flow

```typescript
// In the purchase service, after successful order creation:

const eventBus = new EventBus();
registerPurchaseListeners(eventBus);

// After order is created:
await eventBus.emit({
  type: 'TicketPurchased',
  timestamp: new Date(),
  payload: {
    orderId: order.id,
    userId: request.userId,
    eventId: request.eventId,
    eventName: event.name,
    ticketType: request.ticketType,
    quantity: request.quantity,
    totalInCents,
  },
});
```

### Test It

```typescript
// src/patterns/event-bus.test.ts

import { EventBus, DomainEvent } from './event-bus';

describe('EventBus', () => {
  let bus: EventBus;

  beforeEach(() => {
    bus = new EventBus();
  });

  it('delivers events to all registered handlers', async () => {
    const calls: string[] = [];

    bus.on('TestEvent', async () => { calls.push('handler1'); });
    bus.on('TestEvent', async () => { calls.push('handler2'); });

    await bus.emit({
      type: 'TestEvent',
      timestamp: new Date(),
      payload: {},
    });

    expect(calls).toEqual(['handler1', 'handler2']);
  });

  it('does not crash when a handler fails', async () => {
    const calls: string[] = [];

    bus.on('TestEvent', async () => { throw new Error('boom'); });
    bus.on('TestEvent', async () => { calls.push('handler2'); });

    const result = await bus.emit({
      type: 'TestEvent',
      timestamp: new Date(),
      payload: {},
    });

    expect(result.successes).toBe(1);
    expect(result.failures).toBe(1);
    expect(calls).toEqual(['handler2']); // Second handler still ran
  });

  it('ignores events with no handlers', async () => {
    const result = await bus.emit({
      type: 'NoHandlers',
      timestamp: new Date(),
      payload: {},
    });

    expect(result.successes).toBe(0);
    expect(result.failures).toBe(0);
  });

  it('allows removing handlers', async () => {
    const calls: string[] = [];
    const handler = async () => { calls.push('called'); };

    bus.on('TestEvent', handler);
    bus.off('TestEvent', handler);

    await bus.emit({
      type: 'TestEvent',
      timestamp: new Date(),
      payload: {},
    });

    expect(calls).toEqual([]);
  });
});
```

```bash
npx jest src/patterns/event-bus.test.ts
```

**Why this matters:** Adding a new side effect (Slack notification, webhook, audit log) requires zero changes to the purchase flow. You write a listener and register it. The producer and consumers are decoupled.

---

## 3. Repository Pattern: Abstract Data Access

**Problem:** TicketPulse's services directly use `pool.query()`. Tests need a running Postgres instance. Switching to a different data store requires changing every service.

**Solution:** Define a `Repository` interface oriented around the domain. Implement it for Postgres in production and in-memory for tests.

### Build: EventRepository Interface + Two Implementations

```typescript
// src/patterns/event-repository.ts

import { Event } from './types';

export interface EventRepository {
  findById(id: string): Promise<Event | null>;
  findByCategory(category: string): Promise<Event[]>;
  save(event: Event): Promise<void>;
  delete(id: string): Promise<void>;
}
```

```typescript
// src/patterns/postgres-event-repository.ts

import { Pool } from 'pg';
import { Event } from './types';
import { EventRepository } from './event-repository';

export class PostgresEventRepository implements EventRepository {
  constructor(private pool: Pool) {}

  async findById(id: string): Promise<Event | null> {
    const result = await this.pool.query(
      'SELECT * FROM events WHERE id = $1',
      [id]
    );
    return result.rows[0] ? this.toEvent(result.rows[0]) : null;
  }

  async findByCategory(category: string): Promise<Event[]> {
    const result = await this.pool.query(
      'SELECT * FROM events WHERE category = $1 ORDER BY starts_at',
      [category]
    );
    return result.rows.map(row => this.toEvent(row));
  }

  async save(event: Event): Promise<void> {
    await this.pool.query(
      `INSERT INTO events (id, name, base_price_cents, category, starts_at)
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT (id) DO UPDATE
       SET name = $2, base_price_cents = $3, category = $4, starts_at = $5`,
      [event.id, event.name, event.basePriceCents, event.category, event.startsAt]
    );
  }

  async delete(id: string): Promise<void> {
    await this.pool.query('DELETE FROM events WHERE id = $1', [id]);
  }

  private toEvent(row: any): Event {
    return {
      id: row.id,
      name: row.name,
      basePriceCents: row.base_price_cents,
      category: row.category,
      startsAt: new Date(row.starts_at),
    };
  }
}
```

```typescript
// src/patterns/in-memory-event-repository.ts

import { Event } from './types';
import { EventRepository } from './event-repository';

export class InMemoryEventRepository implements EventRepository {
  private events = new Map<string, Event>();

  async findById(id: string): Promise<Event | null> {
    return this.events.get(id) ?? null;
  }

  async findByCategory(category: string): Promise<Event[]> {
    return [...this.events.values()]
      .filter(e => e.category === category)
      .sort((a, b) => a.startsAt.getTime() - b.startsAt.getTime());
  }

  async save(event: Event): Promise<void> {
    this.events.set(event.id, { ...event });
  }

  async delete(id: string): Promise<void> {
    this.events.delete(id);
  }

  // Test helper: seed data
  seed(events: Event[]): void {
    for (const event of events) {
      this.events.set(event.id, { ...event });
    }
  }

  // Test helper: inspect state
  getAll(): Event[] {
    return [...this.events.values()];
  }
}
```

### Test It

```typescript
// src/patterns/event-repository.test.ts

import { InMemoryEventRepository } from './in-memory-event-repository';
import { Event } from './types';

describe('EventRepository (InMemory)', () => {
  let repo: InMemoryEventRepository;

  const concert: Event = {
    id: 'evt-1',
    name: 'Summer Concert',
    basePriceCents: 10000,
    category: 'concert',
    startsAt: new Date('2026-07-15'),
  };

  const conference: Event = {
    id: 'evt-2',
    name: 'Tech Conf',
    basePriceCents: 50000,
    category: 'conference',
    startsAt: new Date('2026-09-01'),
  };

  beforeEach(() => {
    repo = new InMemoryEventRepository();
    repo.seed([concert, conference]);
  });

  it('finds an event by ID', async () => {
    const found = await repo.findById('evt-1');
    expect(found?.name).toBe('Summer Concert');
  });

  it('returns null for missing event', async () => {
    const found = await repo.findById('nope');
    expect(found).toBeNull();
  });

  it('filters events by category', async () => {
    const concerts = await repo.findByCategory('concert');
    expect(concerts).toHaveLength(1);
    expect(concerts[0].name).toBe('Summer Concert');
  });

  it('saves a new event', async () => {
    const newEvent: Event = {
      id: 'evt-3',
      name: 'Basketball Game',
      basePriceCents: 7500,
      category: 'sports',
      startsAt: new Date('2026-11-20'),
    };

    await repo.save(newEvent);
    const found = await repo.findById('evt-3');
    expect(found?.name).toBe('Basketball Game');
  });

  it('deletes an event', async () => {
    await repo.delete('evt-1');
    const found = await repo.findById('evt-1');
    expect(found).toBeNull();
  });
});
```

```bash
npx jest src/patterns/event-repository.test.ts
```

**Why this matters:** Your service code depends on `EventRepository` (the interface), not `PostgresEventRepository` (the implementation). In tests, inject `InMemoryEventRepository`. In production, inject `PostgresEventRepository`. The service does not know or care which one it gets.

---

## 4. Decorator Pattern: Add Logging and Caching Without Modification

**Problem:** You need to add logging to every `EventRepository` call for debugging. You also need caching for `findById` because the same event is fetched hundreds of times per minute. But you do not want to pollute `PostgresEventRepository` with logging and caching logic -- those are separate concerns.

**Solution:** Wrap the repository with decorators. Each decorator adds one behavior and delegates to the inner repository.

### Build: LoggingDecorator

```typescript
// src/patterns/logging-event-repository.ts

import { Event } from './types';
import { EventRepository } from './event-repository';

export class LoggingEventRepository implements EventRepository {
  constructor(
    private inner: EventRepository,
    private logger: { info: (msg: string, meta?: any) => void } = console
  ) {}

  async findById(id: string): Promise<Event | null> {
    const start = Date.now();
    const result = await this.inner.findById(id);
    const duration = Date.now() - start;

    this.logger.info('EventRepository.findById', {
      id,
      found: result !== null,
      durationMs: duration,
    });

    return result;
  }

  async findByCategory(category: string): Promise<Event[]> {
    const start = Date.now();
    const results = await this.inner.findByCategory(category);
    const duration = Date.now() - start;

    this.logger.info('EventRepository.findByCategory', {
      category,
      count: results.length,
      durationMs: duration,
    });

    return results;
  }

  async save(event: Event): Promise<void> {
    this.logger.info('EventRepository.save', { eventId: event.id, name: event.name });
    await this.inner.save(event);
  }

  async delete(id: string): Promise<void> {
    this.logger.info('EventRepository.delete', { id });
    await this.inner.delete(id);
  }
}
```

### Build: CachingDecorator

```typescript
// src/patterns/caching-event-repository.ts

import { Event } from './types';
import { EventRepository } from './event-repository';

export class CachingEventRepository implements EventRepository {
  private cache = new Map<string, { event: Event; expiresAt: number }>();

  constructor(
    private inner: EventRepository,
    private ttlMs: number = 60_000 // 1 minute default
  ) {}

  async findById(id: string): Promise<Event | null> {
    // Check cache
    const cached = this.cache.get(id);
    if (cached && Date.now() < cached.expiresAt) {
      return cached.event;
    }

    // Cache miss: fetch from inner
    const event = await this.inner.findById(id);
    if (event) {
      this.cache.set(id, {
        event,
        expiresAt: Date.now() + this.ttlMs,
      });
    }

    return event;
  }

  async findByCategory(category: string): Promise<Event[]> {
    // Category queries are not cached -- too many variations
    return this.inner.findByCategory(category);
  }

  async save(event: Event): Promise<void> {
    await this.inner.save(event);
    // Invalidate cache entry on write
    this.cache.delete(event.id);
  }

  async delete(id: string): Promise<void> {
    await this.inner.delete(id);
    this.cache.delete(id);
  }

  // Test helper
  cacheSize(): number {
    return this.cache.size;
  }
}
```

### Build: Compose the Decorators

```typescript
// src/patterns/composition.ts
// This is the composition root -- where you wire everything together

import { EventRepository } from './event-repository';
import { PostgresEventRepository } from './postgres-event-repository';
import { CachingEventRepository } from './caching-event-repository';
import { LoggingEventRepository } from './logging-event-repository';
import { Pool } from 'pg';

export function createEventRepository(pool: Pool): EventRepository {
  // Inner-most: real data access
  const postgres = new PostgresEventRepository(pool);

  // Middle: add caching (60 second TTL)
  const cached = new CachingEventRepository(postgres, 60_000);

  // Outer: add logging (wraps cached, so we see cache hits as fast queries)
  const logged = new LoggingEventRepository(cached);

  return logged;
}

// The caller just gets an EventRepository. It has no idea that logging
// and caching are happening. The behavior is transparent.
```

### Test It

```typescript
// src/patterns/caching-event-repository.test.ts

import { CachingEventRepository } from './caching-event-repository';
import { InMemoryEventRepository } from './in-memory-event-repository';
import { Event } from './types';

describe('CachingEventRepository', () => {
  const event: Event = {
    id: 'evt-1',
    name: 'Concert',
    basePriceCents: 10000,
    category: 'concert',
    startsAt: new Date('2026-07-15'),
  };

  it('returns cached result on second findById call', async () => {
    const inner = new InMemoryEventRepository();
    inner.seed([event]);
    const cached = new CachingEventRepository(inner, 60_000);

    // First call: cache miss
    const result1 = await cached.findById('evt-1');
    expect(result1?.name).toBe('Concert');
    expect(cached.cacheSize()).toBe(1);

    // Delete from inner -- cached version should still be returned
    await inner.delete('evt-1');
    const result2 = await cached.findById('evt-1');
    expect(result2?.name).toBe('Concert'); // Served from cache
  });

  it('invalidates cache on save', async () => {
    const inner = new InMemoryEventRepository();
    inner.seed([event]);
    const cached = new CachingEventRepository(inner, 60_000);

    // Populate cache
    await cached.findById('evt-1');
    expect(cached.cacheSize()).toBe(1);

    // Save clears cache
    await cached.save({ ...event, name: 'Updated Concert' });
    expect(cached.cacheSize()).toBe(0);

    // Next fetch gets the updated version
    const result = await cached.findById('evt-1');
    expect(result?.name).toBe('Updated Concert');
  });
});
```

```bash
npx jest src/patterns/caching-event-repository.test.ts
```

**Why this matters:** `PostgresEventRepository` is never modified. It does not know about caching or logging. Each concern is a separate, testable class. You can swap the caching strategy, change the logging format, or remove either decorator without touching the others.

---

## 5. Factory Pattern: Notification Delivery

**Problem:** TicketPulse sends notifications via email, SMS, or push depending on user preferences. The code that sends a notification should not know the details of each delivery method.

**Solution:** A factory function creates the right sender based on the user's preference.

### Build: NotificationSender Interface + Implementations

```typescript
// src/notifications/notification-sender.ts

export interface NotificationSender {
  send(to: string, subject: string, body: string): Promise<void>;
}

export class EmailNotificationSender implements NotificationSender {
  async send(to: string, subject: string, body: string): Promise<void> {
    console.log(`[EMAIL] To: ${to} | Subject: ${subject}`);
    // In production: await emailService.send(to, subject, body)
  }
}

export class SmsNotificationSender implements NotificationSender {
  async send(to: string, subject: string, body: string): Promise<void> {
    // SMS does not have a subject -- prepend it to the body
    const message = `${subject}: ${body}`;
    console.log(`[SMS] To: ${to} | Message: ${message.substring(0, 160)}`);
    // In production: await smsService.send(to, message)
  }
}

export class PushNotificationSender implements NotificationSender {
  async send(to: string, subject: string, body: string): Promise<void> {
    console.log(`[PUSH] Token: ${to} | Title: ${subject}`);
    // In production: await pushService.send(to, { title: subject, body })
  }
}
```

### Build: NotificationFactory

```typescript
// src/notifications/notification-factory.ts

import {
  NotificationSender,
  EmailNotificationSender,
  SmsNotificationSender,
  PushNotificationSender,
} from './notification-sender';

export type NotificationType = 'email' | 'sms' | 'push';

export class NotificationFactory {
  private static senders = new Map<NotificationType, NotificationSender>([
    ['email', new EmailNotificationSender()],
    ['sms', new SmsNotificationSender()],
    ['push', new PushNotificationSender()],
  ]);

  static create(type: NotificationType): NotificationSender {
    const sender = this.senders.get(type);
    if (!sender) {
      throw new Error(`Unknown notification type: ${type}`);
    }
    return sender;
  }

  // Allow registering custom senders (for testing or new channels)
  static register(type: NotificationType, sender: NotificationSender): void {
    this.senders.set(type, sender);
  }
}
```

### Build: Use It in TicketPulse

```typescript
// src/notifications/notify-user.ts

import { NotificationFactory, NotificationType } from './notification-factory';
import { User } from '../patterns/types';

export async function notifyUser(
  user: User,
  subject: string,
  body: string
): Promise<void> {
  const sender = NotificationFactory.create(user.notificationPreference);

  // Pick the right delivery address based on preference
  let to: string;
  switch (user.notificationPreference) {
    case 'email':
      to = user.email;
      break;
    case 'sms':
      if (!user.phone) throw new Error(`User ${user.id} has no phone number`);
      to = user.phone;
      break;
    case 'push':
      if (!user.pushToken) throw new Error(`User ${user.id} has no push token`);
      to = user.pushToken;
      break;
  }

  await sender.send(to, subject, body);
}
```

### Test It

```typescript
// src/notifications/notification-factory.test.ts

import { NotificationFactory } from './notification-factory';
import { NotificationSender } from './notification-sender';

describe('NotificationFactory', () => {
  it('creates an email sender', () => {
    const sender = NotificationFactory.create('email');
    expect(sender).toBeDefined();
  });

  it('creates an SMS sender', () => {
    const sender = NotificationFactory.create('sms');
    expect(sender).toBeDefined();
  });

  it('creates a push sender', () => {
    const sender = NotificationFactory.create('push');
    expect(sender).toBeDefined();
  });

  it('throws for unknown type', () => {
    expect(() => NotificationFactory.create('pigeon' as any)).toThrow(
      'Unknown notification type: pigeon'
    );
  });

  it('allows registering custom senders', async () => {
    const calls: string[] = [];
    const fakeSender: NotificationSender = {
      send: async (to, subject) => { calls.push(`${to}:${subject}`); },
    };

    NotificationFactory.register('email', fakeSender);
    const sender = NotificationFactory.create('email');
    await sender.send('test@example.com', 'Hello', 'World');

    expect(calls).toEqual(['test@example.com:Hello']);
  });
});
```

```bash
npx jest src/notifications/notification-factory.test.ts
```

**Why this matters:** Adding a fourth notification channel (Slack, WhatsApp, carrier pigeon) requires one new class implementing `NotificationSender` and one line to register it. The calling code does not change.

---

## 6. Design: Where Else Could You Apply These?

Take 5 minutes and think about TicketPulse. Where else could these patterns solve a real problem?

| Pattern | Potential Application |
|---------|----------------------|
| **Strategy** | Refund policies (full refund, partial, no refund depending on timing) |
| **Observer** | OrderCancelled triggers refund, email, inventory release |
| **Repository** | UserRepository, VenueRepository |
| **Decorator** | Rate limiting on API endpoints, retry logic on external calls |
| **Factory** | PaymentGateway.create('stripe' \| 'paypal') based on region |

> **Draw it:** Sketch the before/after for one of these. What classes exist? What depends on what? How does adding a new variant work in each?

---

## 7. Common Mistake: Pattern Overuse

> "When you have a hammer, everything looks like a nail."

Patterns have costs:
- **Indirection**: More files, more jumps to understand the flow
- **Abstraction overhead**: Interfaces, factories, registries add lines of code
- **Naming burden**: `CachingLoggingEventRepositoryFactory` is not readable

**Rules of thumb:**
- If you have **one** implementation and no signal a second is coming, skip the pattern. Use it directly.
- If you have **two** implementations, a simple `if/else` is fine.
- If you have **three or more**, the pattern earns its keep.
- If the pattern makes the code **harder** to understand, remove it. Simplicity wins.

---

## Checklist

Before moving on, confirm:

- [ ] PricingStrategy interface with 4 implementations, all tested
- [ ] EventBus with handlers for email, analytics, inventory, and Slack
- [ ] EventRepository interface with Postgres and InMemory implementations
- [ ] LoggingDecorator and CachingDecorator wrapping EventRepository
- [ ] NotificationFactory returning the right sender based on user preference
- [ ] All tests pass
- [ ] You can explain when each pattern is overkill

---

## What's Next

In L1-M16d, we zoom out from individual classes to module-level design: coupling, cohesion, dependency cycles, and what a modular monolith looks like for TicketPulse.
