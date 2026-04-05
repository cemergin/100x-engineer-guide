# L2-M51a: Composition Over Inheritance & FP vs OOP

> **Loop 2 (Practice)** | Section 2D: Advanced Patterns | ⏱️ 60 min | 🟡 Deep Dive | Prerequisites: L1-M16a (SOLID Principles in Practice)
>
> **Source:** Chapters 3, 22, 25, 32, 13 of the 100x Engineer Guide

> **Before you continue:** When you need to add new behavior to existing code, do you reach for class inheritance or function composition first? Think about a real example from your experience — which approach would have been simpler?

---

## The Goal

TicketPulse's service layer has accumulated a five-level inheritance chain: `BaseService` -> `AuthenticatedService` -> `LoggingService` -> `CachedService` -> `EventService`. It was built with good intentions -- each level adds a cross-cutting concern. But it has become rigid. Need caching without auth? Impossible. Need logging without caching? Fork the hierarchy.

This module replaces the hierarchy with composition, then introduces functional programming patterns for TicketPulse's pricing logic. You will feel the rigidity of deep inheritance, then feel the flexibility of composition.

**You will run code within the first two minutes.**

---

## 0. The Inheritance Problem (5 minutes)

Here is what has accumulated over six months of development:

```typescript
// src/services/base.service.ts
// Level 1: Database connection
export abstract class BaseService {
  constructor(protected db: Pool) {}

  protected async query<T>(sql: string, params?: any[]): Promise<T[]> {
    const result = await this.db.query(sql, params);
    return result.rows;
  }
}

// src/services/authenticated.service.ts
// Level 2: Auth checks
export abstract class AuthenticatedService extends BaseService {
  constructor(db: Pool, protected authProvider: AuthProvider) {
    super(db);
  }

  protected async requireAuth(userId: string): Promise<User> {
    const user = await this.authProvider.getUser(userId);
    if (!user) throw new UnauthorizedError('User not found');
    return user;
  }

  protected async requireRole(userId: string, role: string): Promise<User> {
    const user = await this.requireAuth(userId);
    if (!user.roles.includes(role)) throw new ForbiddenError(`Requires role: ${role}`);
    return user;
  }
}

// src/services/logging.service.ts
// Level 3: Method-level logging
export abstract class LoggingService extends AuthenticatedService {
  constructor(db: Pool, authProvider: AuthProvider, protected logger: Logger) {
    super(db, authProvider);
  }

  protected log(method: string, data: Record<string, any>): void {
    this.logger.info({ service: this.constructor.name, method, ...data });
  }
}

// src/services/cached.service.ts
// Level 4: Cache layer
export abstract class CachedService extends LoggingService {
  constructor(
    db: Pool,
    authProvider: AuthProvider,
    logger: Logger,
    protected cache: CacheClient
  ) {
    super(db, authProvider, logger);
  }

  protected async cached<T>(key: string, ttlSeconds: number, fn: () => Promise<T>): Promise<T> {
    const hit = await this.cache.get(key);
    if (hit) return JSON.parse(hit);
    const result = await fn();
    await this.cache.set(key, JSON.stringify(result), ttlSeconds);
    return result;
  }
}

// src/services/event.service.ts
// Level 5: The actual business logic
export class EventService extends CachedService {
  constructor(
    db: Pool,
    authProvider: AuthProvider,
    logger: Logger,
    cache: CacheClient
  ) {
    super(db, authProvider, logger, cache);
  }

  async getEvent(eventId: string): Promise<Event> {
    this.log('getEvent', { eventId });
    return this.cached(`event:${eventId}`, 60, async () => {
      const rows = await this.query<Event>('SELECT * FROM events WHERE id = $1', [eventId]);
      if (rows.length === 0) throw new NotFoundError('Event not found');
      return rows[0];
    });
  }

  async createEvent(userId: string, data: CreateEventInput): Promise<Event> {
    await this.requireRole(userId, 'organizer');
    this.log('createEvent', { userId, eventName: data.name });
    // ... business logic
  }
}
```

---

## 1. Debug: Trace the Inheritance Chain (5 minutes)

Answer these questions by reading the code above:

1. **How many constructor parameters does `EventService` need?** Count them. Four: `db`, `authProvider`, `logger`, `cache`. Every level adds a parameter. Level 6 would need five.

2. **What if you need a `PublicEventService` that has caching and logging but NOT authentication?** (Public event listing does not require a logged-in user.) You cannot skip `AuthenticatedService` -- it is in the middle of the chain. Your options are all bad:
   - Duplicate the caching and logging logic in a parallel hierarchy
   - Pass a dummy auth provider that always returns a guest user
   - Accept that public endpoints carry unused auth machinery

3. **What if you need to add rate limiting?** Where in the hierarchy does it go? Before caching? After auth? The linear hierarchy forces a single ordering. Different services might need different orderings.

4. **What happens when `BaseService.query()` changes its signature?** Every class in the chain is affected. Five files touched for one change.

This is the **fragile base class problem**: changes to any level ripple through all descendants.

> **Reflect:** At what point did this hierarchy become a problem? It was probably fine at two levels. By five, it is clearly rigid. The lesson: inheritance hierarchies tend to grow, and each level makes them harder to change.

---

## 2. Build: Replace with Composition (15 minutes)

Extract each concern as an independent, injectable component. No inheritance.

```typescript
// src/middleware/with-auth.ts

export interface AuthMiddleware {
  requireAuth(userId: string): Promise<User>;
  requireRole(userId: string, role: string): Promise<User>;
}

export class AuthMiddlewareImpl implements AuthMiddleware {
  constructor(private authProvider: AuthProvider) {}

  async requireAuth(userId: string): Promise<User> {
    const user = await this.authProvider.getUser(userId);
    if (!user) throw new UnauthorizedError('User not found');
    return user;
  }

  async requireRole(userId: string, role: string): Promise<User> {
    const user = await this.requireAuth(userId);
    if (!user.roles.includes(role)) throw new ForbiddenError(`Requires role: ${role}`);
    return user;
  }
}
```

```typescript
// src/middleware/with-logging.ts

export interface LoggingMiddleware {
  log(method: string, data: Record<string, any>): void;
  withLogging<T>(method: string, data: Record<string, any>, fn: () => Promise<T>): Promise<T>;
}

export class LoggingMiddlewareImpl implements LoggingMiddleware {
  constructor(
    private logger: Logger,
    private serviceName: string
  ) {}

  log(method: string, data: Record<string, any>): void {
    this.logger.info({ service: this.serviceName, method, ...data });
  }

  async withLogging<T>(method: string, data: Record<string, any>, fn: () => Promise<T>): Promise<T> {
    this.log(method, { ...data, phase: 'start' });
    const start = Date.now();
    try {
      const result = await fn();
      this.log(method, { ...data, phase: 'end', durationMs: Date.now() - start });
      return result;
    } catch (error: any) {
      this.log(method, { ...data, phase: 'error', error: error.message, durationMs: Date.now() - start });
      throw error;
    }
  }
}
```

```typescript
// src/middleware/with-caching.ts

export interface CachingMiddleware {
  cached<T>(key: string, ttlSeconds: number, fn: () => Promise<T>): Promise<T>;
  invalidate(key: string): Promise<void>;
}

export class CachingMiddlewareImpl implements CachingMiddleware {
  constructor(private cache: CacheClient) {}

  async cached<T>(key: string, ttlSeconds: number, fn: () => Promise<T>): Promise<T> {
    const hit = await this.cache.get(key);
    if (hit) return JSON.parse(hit);
    const result = await fn();
    await this.cache.set(key, JSON.stringify(result), ttlSeconds);
    return result;
  }

  async invalidate(key: string): Promise<void> {
    await this.cache.del(key);
  }
}
```

Now `EventService` composes only what it needs:

```typescript
// src/services/event.service.ts (composed)

export class EventService {
  constructor(
    private db: Pool,
    private auth: AuthMiddleware,
    private logging: LoggingMiddleware,
    private caching: CachingMiddleware
  ) {}

  async getEvent(eventId: string): Promise<Event> {
    return this.logging.withLogging('getEvent', { eventId }, () =>
      this.caching.cached(`event:${eventId}`, 60, async () => {
        const result = await this.db.query('SELECT * FROM events WHERE id = $1', [eventId]);
        if (result.rows.length === 0) throw new NotFoundError('Event not found');
        return result.rows[0];
      })
    );
  }

  async createEvent(userId: string, data: CreateEventInput): Promise<Event> {
    await this.auth.requireRole(userId, 'organizer');
    return this.logging.withLogging('createEvent', { userId }, async () => {
      // ... business logic
    });
  }
}
```

And the public event service? No problem:

```typescript
// src/services/public-event.service.ts
// Caching and logging, but NO auth

export class PublicEventService {
  constructor(
    private db: Pool,
    private logging: LoggingMiddleware,
    private caching: CachingMiddleware
    // No auth -- this service does not need it
  ) {}

  async getEvent(eventId: string): Promise<Event> {
    return this.logging.withLogging('getEvent', { eventId }, () =>
      this.caching.cached(`event:${eventId}`, 300, async () => {
        const result = await this.db.query(
          `SELECT * FROM events WHERE id = $1 AND status = 'published'`,
          [eventId]
        );
        if (result.rows.length === 0) throw new NotFoundError('Event not found');
        return result.rows[0];
      })
    );
  }
}
```

Wiring it all together at the composition root:

```typescript
// src/main.ts -- the composition root

const db = new Pool({ connectionString: process.env.DATABASE_URL });
const authProvider = new JwtAuthProvider(process.env.JWT_SECRET!);
const logger = createLogger('ticketpulse');
const cache = new Redis(process.env.REDIS_URL!);

// Build the middleware pieces
const auth = new AuthMiddlewareImpl(authProvider);
const logging = new LoggingMiddlewareImpl(logger, 'EventService');
const caching = new CachingMiddlewareImpl(cache);

// Compose services with exactly the middleware they need
const eventService = new EventService(db, auth, logging, caching);
const publicEventService = new PublicEventService(db, logging, caching);
```

No inheritance. Each service declares exactly what it needs. Adding rate limiting means creating a `RateLimitMiddleware` and injecting it into the services that need it -- no hierarchy modification required.

```bash
git add -A && git commit -m "refactor: replace service inheritance hierarchy with composition"
```

---

## 3. The Decorator Pattern Alternative (5 minutes)

Another composition approach: wrap the service interface with decorators. Each decorator adds one behavior:

```typescript
// The core interface
interface EventReader {
  getEvent(eventId: string): Promise<Event>;
}

// Bare implementation
class PostgresEventReader implements EventReader {
  constructor(private db: Pool) {}
  async getEvent(eventId: string): Promise<Event> {
    const result = await this.db.query('SELECT * FROM events WHERE id = $1', [eventId]);
    return result.rows[0];
  }
}

// Logging decorator
class LoggingEventReader implements EventReader {
  constructor(private inner: EventReader, private logger: Logger) {}
  async getEvent(eventId: string): Promise<Event> {
    this.logger.info({ method: 'getEvent', eventId });
    const result = await this.inner.getEvent(eventId);
    this.logger.info({ method: 'getEvent', eventId, found: !!result });
    return result;
  }
}

// Caching decorator
class CachingEventReader implements EventReader {
  constructor(private inner: EventReader, private cache: CacheClient) {}
  async getEvent(eventId: string): Promise<Event> {
    const cached = await this.cache.get(`event:${eventId}`);
    if (cached) return JSON.parse(cached);
    const result = await this.inner.getEvent(eventId);
    await this.cache.set(`event:${eventId}`, JSON.stringify(result), 60);
    return result;
  }
}

// Compose in any order:
const reader: EventReader = new CachingEventReader(
  new LoggingEventReader(
    new PostgresEventReader(db),
    logger
  ),
  cache
);
```

This is the same principle -- composition over inheritance -- expressed differently. Choose whichever pattern fits your team's codebase conventions.

---

## 4. The Pricing Pipeline as FP (15 minutes)

TicketPulse calculates ticket prices through multiple steps: base price, early bird discount, volume discount, service fee, tax. Currently this is a single function with 80 lines of interleaved logic. Rewrite it as a pipeline of pure functions.

First, define the pipeline helper:

```typescript
// src/utils/pipe.ts

// pipe: compose functions left-to-right
// pipe(f, g, h)(x) === h(g(f(x)))
export function pipe<T>(...fns: Array<(arg: T) => T>): (arg: T) => T {
  return (arg: T) => fns.reduce((result, fn) => fn(result), arg);
}

// For async functions:
export function pipeAsync<T>(...fns: Array<(arg: T) => T | Promise<T>>): (arg: T) => Promise<T> {
  return async (arg: T) => {
    let result = arg;
    for (const fn of fns) {
      result = await fn(result);
    }
    return result;
  };
}
```

Now the pricing context and each step:

```typescript
// src/pricing/types.ts

export interface PricingContext {
  basePriceCents: number;
  quantity: number;
  currentPriceCents: number;  // running total per ticket
  totalCents: number;         // running total for the order
  appliedDiscounts: string[]; // audit trail of what was applied
  purchaseDate: Date;
  eventDate: Date;
  userId: string;
  tierName: string;
}
```

```typescript
// src/pricing/steps.ts
// Each function is PURE: takes a PricingContext, returns a new PricingContext.
// No side effects. No database calls. No external state.

export function getBasePrice(ctx: PricingContext): PricingContext {
  return {
    ...ctx,
    currentPriceCents: ctx.basePriceCents,
    totalCents: ctx.basePriceCents * ctx.quantity,
  };
}

export function applyEarlyBirdDiscount(ctx: PricingContext): PricingContext {
  const daysUntilEvent = Math.floor(
    (ctx.eventDate.getTime() - ctx.purchaseDate.getTime()) / (1000 * 60 * 60 * 24)
  );

  if (daysUntilEvent < 30) return ctx;  // No discount within 30 days

  // --- YOUR DECISION POINT ---
  // How aggressive should the early bird discount be?
  // Option A: flat 20% for any purchase > 30 days out
  // Option B: tiered (10% at 30 days, 15% at 60 days, 20% at 90+ days)
  // Option C: dynamic based on demand (high demand = smaller discount)
  //
  // Implement Option B:

  let discountRate: number;
  if (daysUntilEvent >= 90) discountRate = 0.20;
  else if (daysUntilEvent >= 60) discountRate = 0.15;
  else discountRate = 0.10;

  const discountedPrice = Math.round(ctx.currentPriceCents * (1 - discountRate));
  return {
    ...ctx,
    currentPriceCents: discountedPrice,
    totalCents: discountedPrice * ctx.quantity,
    appliedDiscounts: [...ctx.appliedDiscounts, `early_bird_${Math.round(discountRate * 100)}pct`],
  };
}

export function applyVolumeDiscount(ctx: PricingContext): PricingContext {
  if (ctx.quantity < 5) return ctx;  // No discount for small orders

  let discountRate: number;
  if (ctx.quantity >= 20) discountRate = 0.15;
  else if (ctx.quantity >= 10) discountRate = 0.10;
  else discountRate = 0.05;

  const discountedTotal = Math.round(ctx.totalCents * (1 - discountRate));
  return {
    ...ctx,
    totalCents: discountedTotal,
    appliedDiscounts: [...ctx.appliedDiscounts, `volume_${Math.round(discountRate * 100)}pct`],
  };
}

export function addServiceFee(ctx: PricingContext): PricingContext {
  // Flat service fee: $2.50 per ticket
  const feeCents = 250 * ctx.quantity;
  return {
    ...ctx,
    totalCents: ctx.totalCents + feeCents,
    appliedDiscounts: [...ctx.appliedDiscounts, 'service_fee'],
  };
}

export function addTax(ctx: PricingContext): PricingContext {
  // Tax rate: 8.5% (in production, this would depend on venue location)
  const taxRate = 0.085;
  const taxCents = Math.round(ctx.totalCents * taxRate);
  return {
    ...ctx,
    totalCents: ctx.totalCents + taxCents,
    appliedDiscounts: [...ctx.appliedDiscounts, `tax_${taxRate * 100}pct`],
  };
}
```

Compose them:

```typescript
// src/pricing/calculate-price.ts

import { pipe } from '../utils/pipe';
import {
  getBasePrice,
  applyEarlyBirdDiscount,
  applyVolumeDiscount,
  addServiceFee,
  addTax
} from './steps';
import { PricingContext } from './types';

export const calculatePrice = pipe<PricingContext>(
  getBasePrice,
  applyEarlyBirdDiscount,
  applyVolumeDiscount,
  addServiceFee,
  addTax
);

// Usage:
const result = calculatePrice({
  basePriceCents: 5000,
  quantity: 10,
  currentPriceCents: 0,
  totalCents: 0,
  appliedDiscounts: [],
  purchaseDate: new Date(),
  eventDate: new Date('2026-09-01'),
  userId: 'user_1',
  tierName: 'General',
});

console.log(result.totalCents);        // Final price
console.log(result.appliedDiscounts);  // ["early_bird_15pct", "volume_10pct", "service_fee", "tax_8.5pct"]
```

**Why this is better:**

1. **Each step is testable in isolation:**

```typescript
describe('applyEarlyBirdDiscount', () => {
  it('gives 20% off for purchases 90+ days before event', () => {
    const ctx = makeContext({
      purchaseDate: new Date('2026-01-01'),
      eventDate: new Date('2026-06-01'),
      currentPriceCents: 5000,
    });
    const result = applyEarlyBirdDiscount(ctx);
    expect(result.currentPriceCents).toBe(4000);  // 20% off
    expect(result.appliedDiscounts).toContain('early_bird_20pct');
  });

  it('gives no discount within 30 days', () => {
    const ctx = makeContext({
      purchaseDate: new Date('2026-05-15'),
      eventDate: new Date('2026-06-01'),
      currentPriceCents: 5000,
    });
    const result = applyEarlyBirdDiscount(ctx);
    expect(result.currentPriceCents).toBe(5000);  // No change
  });
});
```

2. **Steps are composable.** Need a different pipeline for VIP pricing? Build a different pipe:

```typescript
const calculateVipPrice = pipe<PricingContext>(
  getBasePrice,
  applyVipMultiplier,  // VIP gets 2x base, no early bird discount
  addServiceFee,
  addTax
);
```

3. **The audit trail (`appliedDiscounts`) is built-in.** Each step records what it did. No need for separate logging.

4. **No shared mutable state.** Each function returns a new object. The input is never modified. You can run multiple pricing calculations in parallel with zero risk of interference.

---

## 5. When OOP, When FP? (5 minutes)

This is not a religious debate. Each paradigm has clear strengths.

### Use OOP for stateful entities with invariants

The `Order` aggregate has a lifecycle, enforces rules, and manages state transitions:

```typescript
class Order {
  private status: OrderStatus;
  private items: OrderItem[];

  cancel(): void {
    if (this.status === 'shipped') {
      throw new Error('Cannot cancel a shipped order');
    }
    this.status = 'cancelled';
    // invariant: cancelled orders cannot be modified further
  }
}
```

This is naturally OOP. The object encapsulates state and enforces rules about how that state can change. Trying to express this with pure functions leads to awkward code.

### Use FP for stateless transformations

Pricing, validation, data transformations, reporting:

```typescript
// Validation as composed pure functions
const validateOrder = pipe<ValidationResult>(
  validateUserExists,
  validateEventAvailable,
  validateQuantityInRange,
  validatePaymentMethod
);

// Reporting as data transformation
const generateDailyReport = pipe<ReportData>(
  fetchRawOrders,
  filterByDateRange,
  groupByEvent,
  calculateRevenue,
  formatAsTable
);
```

These are naturally FP. No state to manage. Each function transforms data and passes it along.

### The pragmatic middle

| Concern | Paradigm | Why |
|---|---|---|
| Domain entities (Order, Event, User) | OOP | State + invariants + lifecycle |
| Data transformations (pricing, reporting) | FP | Stateless, composable, testable |
| Service layer (OrderService) | OOP shell, FP core | OOP for dependency injection, FP for business logic |
| Middleware (auth, logging, caching) | Either | Composition works with both |
| Configuration | FP (immutable data) | No reason for state to change |

> **Reflect:** Look at TicketPulse's codebase. Identify one place where OOP would be better than the current FP approach, and one place where FP would be better than the current OOP approach.

---

## Checkpoint

Before continuing, verify:

- [ ] Inheritance hierarchy is gone -- each concern is an independent, injectable component
- [ ] `EventService` composes auth, logging, and caching without inheriting from any of them
- [ ] `PublicEventService` uses logging and caching without auth -- impossible with the old hierarchy
- [ ] Pricing pipeline is a chain of pure functions
- [ ] Each pricing step is testable in isolation (no mocks needed)
- [ ] The `pipe` utility works for synchronous function composition

```bash
git add -A && git commit -m "refactor: replace inheritance with composition, rewrite pricing as FP pipeline"
```

---

## Reflect

**The one-sentence summary:** Use objects to define boundaries and manage state. Use functions for the logic within those boundaries. Most real systems need both.

Go and Rust have no class inheritance at all. They use composition plus interfaces (Go) or traits (Rust). This is not a limitation -- it is a deliberate design choice. The fact that two modern systems languages chose to omit inheritance tells you something about where the industry has landed on this question.

---

## Key Terms

| Term | Definition |
|------|-----------|
| **CQRS** | Command Query Responsibility Segregation; a pattern that uses separate models for reading and writing data. |
| **Command** | An operation that changes state in the system (a write) and typically returns no data. |
| **Query** | An operation that returns data without modifying state (a read). |
| **Read model** | A data representation optimized for queries, often denormalized for fast lookups. |
| **Write model** | A data representation optimized for processing commands, enforcing business rules and consistency. |
| **Projection** | The process of transforming events or commands into a read-optimized view of the data. |

---

## What's Next

In **Data Pipelines** (L2-M52), you'll build a data pipeline that moves TicketPulse's event data from operational databases into an analytics warehouse.

---

## Further Reading

- "Design Patterns" by the Gang of Four -- the original source for "Favor composition over inheritance"
- "Boundaries" by Gary Bernhardt -- "Objects are not about state -- objects are about boundaries"
- "Out of the Tar Pit" by Moseley and Marks -- a rigorous analysis of complexity, state, and why FP helps
- The `fp-ts` library for TypeScript -- full functional programming toolkit if you want to go deeper
