# L1-M16d: Coupling, Cohesion & Modularity

> **Loop 1 (Foundation)** | Section 1D: Software Engineering Principles | Duration: 60 min | Tier: Deep Dive
>
> **Prerequisites:** L1-M16a (SOLID Principles), L1-M16c (Design Patterns)
>
> **What you'll build:** You will install dependency-cruiser, visualize TicketPulse's dependency graph, identify and break a dependency cycle, reorganize a low-cohesion `utils/` directory, and design the ideal module boundaries for TicketPulse as a modular monolith.

---

## The Goal

Individual classes can follow SOLID perfectly and still produce a system that is painful to change. The problem is at the module level: which modules depend on which, how tightly they are coupled, and whether the code inside each module belongs together.

This module teaches you to see the forest, not just the trees. You will visualize your dependency graph, identify structural problems, and fix them.

**You will run code within the first two minutes.**

---

## 0. Quick Start (2 minutes)

Install dependency-cruiser and set up the project structure we will analyze:

```bash
cd ticketpulse
npm install -D dependency-cruiser
```

First, let us create a project structure that has deliberate coupling problems to analyze. Create these files:

```bash
mkdir -p src/events src/orders src/users src/notifications src/utils src/shared
```

```typescript
// src/utils/helpers.ts
// A classic "junk drawer" utils file

import { Pool } from 'pg';

// Date formatting -- why is this in utils?
export function formatDate(date: Date): string {
  return date.toISOString().split('T')[0];
}

// Price formatting -- belongs with pricing logic
export function formatCurrency(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

// Email validation -- belongs with user logic
export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// Slug generation -- belongs with event logic
export function generateSlug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}

// Random ID -- generic utility, actually belongs in utils
export function generateId(): string {
  return crypto.randomUUID();
}

// Retry logic -- belongs in shared infrastructure
export async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  delayMs: number = 1000
): Promise<T> {
  let lastError: Error | undefined;
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (attempt < maxRetries - 1) {
        await new Promise(resolve => setTimeout(resolve, delayMs * (attempt + 1)));
      }
    }
  }
  throw lastError;
}

// Pagination -- belongs in shared infrastructure
export interface PaginationParams {
  page: number;
  limit: number;
}

export function buildPaginationQuery(params: PaginationParams): string {
  const offset = (params.page - 1) * params.limit;
  return `LIMIT ${params.limit} OFFSET ${offset}`;
}
```

```typescript
// src/events/event.service.ts
// COUPLING PROBLEM: directly imports from orders module

import { formatDate, generateSlug, formatCurrency } from '../utils/helpers';
import { Order } from '../orders/order.types';  // <-- Cross-module dependency

export interface Event {
  id: string;
  name: string;
  slug: string;
  basePriceCents: number;
  startsAt: Date;
  capacity: number;
  ticketsSold: number;
}

export class EventService {
  private events = new Map<string, Event>();

  async findById(id: string): Promise<Event | null> {
    return this.events.get(id) ?? null;
  }

  async create(name: string, basePriceCents: number, startsAt: Date, capacity: number): Promise<Event> {
    const event: Event = {
      id: crypto.randomUUID(),
      name,
      slug: generateSlug(name),
      basePriceCents,
      startsAt,
      capacity,
      ticketsSold: 0,
    };
    this.events.set(event.id, event);
    return event;
  }

  // COUPLING PROBLEM: EventService knows about Order type
  async getEventRevenue(eventId: string, orders: Order[]): Promise<string> {
    const eventOrders = orders.filter(o => o.eventId === eventId);
    const totalCents = eventOrders.reduce((sum, o) => sum + o.totalInCents, 0);
    return formatCurrency(totalCents);
  }

  async getFormattedDate(eventId: string): Promise<string> {
    const event = await this.findById(eventId);
    if (!event) throw new Error('Event not found');
    return formatDate(event.startsAt);
  }
}
```

```typescript
// src/orders/order.types.ts

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
```

```typescript
// src/orders/order.service.ts
// COUPLING PROBLEM: directly imports from events module

import { EventService, Event } from '../events/event.service';  // <-- Creates a cycle!
import { formatCurrency } from '../utils/helpers';

export class OrderService {
  constructor(private eventService: EventService) {}

  async createOrder(userId: string, eventId: string, quantity: number): Promise<Order> {
    // OrderService depends on EventService
    const event = await this.eventService.findById(eventId);
    if (!event) throw new Error('Event not found');

    const totalInCents = event.basePriceCents * quantity;

    return {
      id: crypto.randomUUID(),
      eventId,
      userId,
      ticketType: 'general',
      quantity,
      totalInCents,
      status: 'pending',
      createdAt: new Date(),
    };
  }

  formatTotal(order: Order): string {
    return formatCurrency(order.totalInCents);
  }
}

// Re-export for convenience (makes the cycle worse)
export type { Order } from './order.types';
```

```typescript
// src/notifications/notification.service.ts
// COUPLING PROBLEM: depends on events AND orders AND users

import { EventService } from '../events/event.service';
import { OrderService } from '../orders/order.service';
import { isValidEmail } from '../utils/helpers';

export class NotificationService {
  constructor(
    private eventService: EventService,
    private orderService: OrderService
  ) {}

  async sendOrderConfirmation(orderId: string, email: string): Promise<void> {
    if (!isValidEmail(email)) {
      throw new Error('Invalid email address');
    }
    console.log(`[EMAIL] Order confirmation sent to ${email}`);
  }
}
```

Now initialize dependency-cruiser:

```bash
npx depcruise --init
```

Choose the TypeScript preset when prompted.

---

## 1. Try It: Visualize the Dependency Graph

Generate a dependency graph for TicketPulse:

```bash
npx depcruise src --include-only "^src" --output-type dot | dot -T svg > dependency-graph.svg
```

If you do not have Graphviz installed (`dot` command):

```bash
# macOS
brew install graphviz

# Then regenerate
npx depcruise src --include-only "^src" --output-type dot | dot -T svg > dependency-graph.svg
```

If you cannot install Graphviz, use text output:

```bash
npx depcruise src --include-only "^src" --output-type text
```

Open the SVG:

```bash
open dependency-graph.svg  # macOS
# or: xdg-open dependency-graph.svg  # Linux
```

> **Observe:** Look at the graph. You should see:
> - `events/event.service.ts` imports from `orders/order.types.ts`
> - `orders/order.service.ts` imports from `events/event.service.ts`
> - This is a **dependency cycle**: events -> orders -> events
> - `utils/helpers.ts` has arrows coming in from everywhere
> - `notifications/notification.service.ts` depends on both events and orders

---

## 2. Coupling Types: TicketPulse Examples

Coupling describes how strongly one module depends on another. From worst to best:

### Content Coupling (Worst)

One module reaches directly into another's internals.

```typescript
// BAD: NotificationService reaches into EventService's internal Map
class NotificationService {
  constructor(private eventService: EventService) {}

  async getEventName(eventId: string): Promise<string> {
    // Accessing private implementation detail
    const event = (this.eventService as any).events.get(eventId);
    return event?.name ?? 'Unknown';
  }
}
```

If `EventService` changes from a `Map` to a database, `NotificationService` breaks. The fix: use the public interface (`eventService.findById()`).

### Stamp Coupling

Passing a whole object when you only need one field.

```typescript
// STAMP COUPLING: We pass the entire Order but only use totalInCents
function formatReceipt(order: Order): string {
  return `Total: $${(order.totalInCents / 100).toFixed(2)}`;
}

// DATA COUPLING (better): Pass only what you need
function formatReceipt(totalInCents: number): string {
  return `Total: $${(totalInCents / 100).toFixed(2)}`;
}
```

Stamp coupling is not always wrong -- passing a domain object can be clearer than passing 8 separate parameters. But across module boundaries, prefer minimal data.

### Control Coupling

One module tells another how to behave via flags.

```typescript
// CONTROL COUPLING: the caller controls internal behavior
async function processOrder(order: Order, skipValidation: boolean): Promise<void> {
  if (!skipValidation) {
    // validate...
  }
  // process...
}

// BETTER: Two separate functions with clear intent
async function processOrder(order: Order): Promise<void> { /* always validates */ }
async function processOrderUnchecked(order: Order): Promise<void> { /* for admin use */ }
```

### Data Coupling (Best)

Modules share only the data they need through explicit parameters.

```typescript
// DATA COUPLING: minimal, explicit dependencies
function calculateTicketPrice(basePriceCents: number, quantity: number): number {
  return basePriceCents * quantity;
}
```

---

## 3. Build: Break the Dependency Cycle

The cycle is: `events/event.service.ts` imports `Order` from `orders/`, and `orders/order.service.ts` imports `EventService` from `events/`. This means you cannot change, test, or deploy either module independently.

### Solution: Extract a Shared Interface

```typescript
// src/shared/event-reader.interface.ts
// Shared interface -- owned by neither module

export interface EventInfo {
  id: string;
  name: string;
  basePriceCents: number;
  startsAt: Date;
  capacity: number;
  ticketsSold: number;
}

export interface EventReader {
  findById(id: string): Promise<EventInfo | null>;
}
```

Now `OrderService` depends on the shared interface, not on `EventService` directly:

```typescript
// src/orders/order.service.ts (fixed)

import { EventReader, EventInfo } from '../shared/event-reader.interface';
import { Order } from './order.types';

export class OrderService {
  constructor(private eventReader: EventReader) {}  // Interface, not concrete class

  async createOrder(userId: string, eventId: string, quantity: number): Promise<Order> {
    const event = await this.eventReader.findById(eventId);
    if (!event) throw new Error('Event not found');

    const totalInCents = event.basePriceCents * quantity;

    return {
      id: crypto.randomUUID(),
      eventId,
      userId,
      ticketType: 'general',
      quantity,
      totalInCents,
      status: 'pending',
      createdAt: new Date(),
    };
  }
}
```

And `EventService` no longer needs to know about `Order`:

```typescript
// src/events/event.service.ts (fixed)

import { generateSlug } from '../utils/slug';  // Specific import, not the junk drawer
import { EventInfo, EventReader } from '../shared/event-reader.interface';

export class EventService implements EventReader {
  private events = new Map<string, EventInfo>();

  async findById(id: string): Promise<EventInfo | null> {
    return this.events.get(id) ?? null;
  }

  async create(
    name: string,
    basePriceCents: number,
    startsAt: Date,
    capacity: number
  ): Promise<EventInfo> {
    const event: EventInfo = {
      id: crypto.randomUUID(),
      name,
      basePriceCents,
      startsAt,
      capacity,
      ticketsSold: 0,
    };
    this.events.set(event.id, event);
    return event;
  }
}

// Revenue calculation moves to a dedicated reporting module
// that depends on BOTH events and orders (which is fine -- it is a leaf module)
```

Regenerate the dependency graph:

```bash
npx depcruise src --include-only "^src" --output-type dot | dot -T svg > dependency-graph-fixed.svg
open dependency-graph-fixed.svg
```

The cycle is gone. `events/` and `orders/` both point to `shared/`, but neither points to the other.

---

## 4. Cohesion: Reorganize the Utils Directory

### Diagnose the Problem

Look at `src/utils/helpers.ts`. It contains:

| Function | Actual Domain |
|----------|--------------|
| `formatDate()` | Date formatting -- shared infrastructure |
| `formatCurrency()` | Price formatting -- shared infrastructure |
| `isValidEmail()` | User validation -- belongs in `users/` |
| `generateSlug()` | URL generation -- belongs in `events/` |
| `generateId()` | ID generation -- shared infrastructure |
| `withRetry()` | Resilience -- shared infrastructure |
| `buildPaginationQuery()` | Query building -- shared infrastructure |

This is **coincidental cohesion** -- the weakest kind. The functions are unrelated; they are in the same file only because someone needed a place to put them.

### Build: Reorganize by Domain

```typescript
// src/users/email-validation.ts
export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}
```

```typescript
// src/events/slug.ts
export function generateSlug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
}
```

```typescript
// src/shared/formatting.ts
export function formatDate(date: Date): string {
  return date.toISOString().split('T')[0];
}

export function formatCurrency(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}
```

```typescript
// src/shared/id.ts
export function generateId(): string {
  return crypto.randomUUID();
}
```

```typescript
// src/shared/retry.ts
export async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  delayMs: number = 1000
): Promise<T> {
  let lastError: Error | undefined;
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (attempt < maxRetries - 1) {
        await new Promise(resolve => setTimeout(resolve, delayMs * (attempt + 1)));
      }
    }
  }
  throw lastError;
}
```

```typescript
// src/shared/pagination.ts
export interface PaginationParams {
  page: number;
  limit: number;
}

export function buildPaginationQuery(params: PaginationParams): string {
  const offset = (params.page - 1) * params.limit;
  return `LIMIT ${params.limit} OFFSET ${offset}`;
}
```

Now delete `src/utils/helpers.ts` and update all imports. Each function lives where it belongs. The `shared/` directory contains only genuinely shared infrastructure code. Domain-specific functions live in their domain modules.

```bash
npx jest --passWithNoTests
```

---

## 5. Design: Module Boundaries for TicketPulse

If TicketPulse grows 10x, what should the module structure look like? This is a **modular monolith** -- a single deployable unit with clear internal boundaries.

```
src/
├── shared/                     # Shared kernel -- stable, changes rarely
│   ├── formatting.ts           # Date/currency formatting
│   ├── id.ts                   # ID generation
│   ├── retry.ts                # Retry/resilience utilities
│   ├── pagination.ts           # Pagination helpers
│   └── event-bus.ts            # Domain event bus
│
├── events/                     # Event management module
│   ├── event.service.ts        # Business logic
│   ├── event.repository.ts     # Data access interface
│   ├── event.types.ts          # Types owned by this module
│   ├── slug.ts                 # Domain-specific utility
│   └── event.routes.ts         # HTTP layer
│
├── orders/                     # Order/purchase module
│   ├── order.service.ts        # Business logic
│   ├── order.repository.ts     # Data access interface
│   ├── order.types.ts          # Types owned by this module
│   ├── pricing/                # Pricing sub-module
│   │   ├── pricing-strategy.ts
│   │   └── pricing-registry.ts
│   └── order.routes.ts         # HTTP layer
│
├── users/                      # User management module
│   ├── user.service.ts
│   ├── user.repository.ts
│   ├── user.types.ts
│   ├── email-validation.ts
│   └── user.routes.ts
│
├── notifications/              # Notification delivery module
│   ├── notification-factory.ts
│   ├── notification-sender.ts
│   └── notification.service.ts
│
├── reporting/                  # Read-only reporting (leaf module)
│   ├── sales-report.service.ts # Depends on orders + events (read-only)
│   └── report.routes.ts
│
└── infrastructure/             # Technical adapters
    ├── postgres/               # Postgres implementations of all repositories
    ├── email/                  # SMTP adapter
    ├── stripe/                 # Payment adapter
    └── config.ts               # Environment configuration
```

### Module Rules

1. **Modules communicate through interfaces**, not concrete classes. `orders/` depends on `EventReader` (interface), not `EventService` (class).

2. **No circular dependencies.** If events depends on orders, orders cannot depend on events. Use shared interfaces or an event bus for cross-module communication.

3. **Each module owns its types.** `Order` is defined in `orders/order.types.ts`, not in a global types file. If another module needs to reference it, it imports the type (types are cheap) or uses a shared interface.

4. **The `shared/` kernel is stable.** It changes infrequently. All modules can depend on it. It depends on nothing else.

5. **`infrastructure/` is unstable (changes often) but depended upon by nothing.** Services depend on repository interfaces; the Postgres implementations in `infrastructure/` are wired up at the composition root.

---

## 6. Package Principles: Stable vs Unstable Modules

Robert C. Martin defined metrics for package health:

**Stability** = how hard it is to change a module (measured by how many other modules depend on it).

| Module | Depended On By | Depends On | Stability | Should It Be Stable? |
|--------|---------------|------------|-----------|---------------------|
| `shared/` | Everything | Nothing | Very stable | Yes -- it is the foundation |
| `events/` | orders, notifications, reporting | shared | Stable | Yes -- core domain |
| `orders/` | notifications, reporting | shared, events (interface) | Moderate | Yes -- core domain |
| `notifications/` | Nothing | shared, orders, users | Unstable | Fine -- leaf module |
| `reporting/` | Nothing | shared, events, orders | Unstable | Fine -- leaf module |
| `infrastructure/` | Nothing directly | Everything (implements interfaces) | Unstable | Fine -- adapters |

**Rule:** Stable modules should be abstract (interfaces, types). Unstable modules should be concrete (implementations). This is the **Stable Abstractions Principle**.

If a module is both stable (many dependents) AND concrete (full of implementation details), you have a problem. A change to that module ripples everywhere. The fix: extract interfaces that dependents can rely on, leaving the implementation in an unstable module.

---

## 7. Reflect

> **If TicketPulse grows 10x, which coupling decisions would you regret? Which are fine?**

**Would regret:**
- `NotificationService` directly importing `EventService` and `OrderService`. When these grow, notification changes will trigger recompilation/retesting of orders and events. Fix: depend on interfaces or use the event bus.
- Everything importing from `utils/helpers.ts`. One change to that file invalidates the build cache for every module.

**Would be fine:**
- `reporting/` depending on `orders/` and `events/` types (read-only, leaf module).
- `shared/` being depended on by everything -- it is small, stable, and abstract.
- `orders/` depending on `EventReader` interface -- this is data coupling, the weakest form.

> **Final thought:** Perfect modularity is not the goal. The goal is that the cost of changing the system grows **linearly** with the size of the change, not exponentially. Good module boundaries achieve that. Bad coupling makes every small change ripple across the codebase.

---

## Checklist

Before moving on, confirm:

- [ ] dependency-cruiser is installed and you can generate a graph
- [ ] You can identify the dependency cycle between events and orders
- [ ] The cycle is broken using a shared interface (`EventReader`)
- [ ] `utils/helpers.ts` is split into domain-specific and shared modules
- [ ] You can explain the difference between content, stamp, control, and data coupling
- [ ] You have a mental model of TicketPulse's ideal module structure
- [ ] You know which modules should be stable and which can be unstable

---

## What's Next

You have now covered the foundational software engineering principles: SOLID, clean code, design patterns, and modularity. These principles are tools, not rules. Apply them when the complexity warrants it. Skip them when simplicity is more valuable. The judgment of *when* to apply *which* principle is what separates a 10x engineer from someone who memorized a textbook.

In Loop 2, you will apply these principles at the system level: architecture patterns, distributed systems, and designing for scale.
