# L1-M20: Domain-Driven Design Basics

> **Loop 1 (Foundation)** | Section 1D: Architecture Fundamentals | ⏱️ 75 min | 🟡 Deep Dive | Prerequisites: L1-M19 (Architecture Patterns Overview)
>
> **Source:** Chapters 1, 3 of the 100x Engineer Guide

---

## The Goal

In M19, you explored architecture styles. But how do you decide where the boundaries go? How do you know which code belongs in which module? How do you avoid building a "big ball of mud" where everything depends on everything?

Domain-Driven Design (DDD) answers these questions. It gives you a structured way to decompose a system based on the business domain — not based on technical layers (controllers, services, repositories) but based on what the business actually does.

This is not academic. The bounded contexts you identify in this module will directly map to the modules you enforce in a modular monolith or the services you extract into microservices. Get the boundaries right, and everything else falls into place. Get them wrong, and you build a distributed monolith.

**You will draw your first context map within ten minutes.**

---

## 1. What Is a Domain? (5 minutes)

TicketPulse's **domain** is live event ticketing. That is the business problem the software solves. The domain includes:

- Events (concerts, shows, festivals)
- Venues (locations with capacities and seat maps)
- Tickets (inventory items that can be purchased)
- Orders (a purchase by a customer)
- Payments (charging money, processing refunds)
- Users (customers, event organizers, admins)
- Notifications (emails, push notifications, SMS)

Notice that the domain is described in business terms, not technical terms. There is no mention of Postgres, Redis, HTTP, or JSON. DDD starts from the business and works toward the code.

---

## 2. Bounded Contexts: Where the Boundaries Go (15 minutes)

A **bounded context** is a boundary within which a particular domain model is defined and consistent. Inside a bounded context, every term has exactly one meaning. Between bounded contexts, the same word can mean different things.

### TicketPulse's Bounded Contexts

```
┌──────────────────────────────────────────────────────────┐
│                      TicketPulse                          │
│                                                          │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────┐ │
│  │    Event       │  │   Ticketing   │  │   Payments   │ │
│  │  Management    │  │               │  │              │ │
│  │               │  │               │  │              │ │
│  │ - Create event│  │ - Inventory   │  │ - Charges    │ │
│  │ - Edit event  │  │ - Seat maps   │  │ - Refunds    │ │
│  │ - Venues      │  │ - Reservations│  │ - Ledger     │ │
│  │ - Artists     │  │ - Purchase    │  │ - Receipts   │ │
│  │ - Categories  │  │   flow        │  │              │ │
│  └───────┬───────┘  └───────┬───────┘  └──────┬───────┘ │
│          │                  │                  │          │
│  ┌───────┴───────┐  ┌──────┴────────┐                   │
│  │    Users      │  │ Notifications │                   │
│  │               │  │               │                   │
│  │ - Profiles    │  │ - Email       │                   │
│  │ - Preferences │  │ - Push        │                   │
│  │ - Auth        │  │ - SMS         │                   │
│  │ - History     │  │ - Templates   │                   │
│  └───────────────┘  └───────────────┘                   │
└──────────────────────────────────────────────────────────┘
```

### How to Identify Bounded Contexts

Ask these questions about each potential context:

1. **Does this group of concepts have its own language?** Event Management talks about "venues," "lineups," and "on-sale dates." Payments talks about "charges," "refunds," and "settlement periods." Different languages suggest different contexts.

2. **Could a different team own this?** If you could imagine a dedicated team responsible for just this area, it is probably a bounded context.

3. **Does this change for different reasons?** Event Management changes when the business adds new event types. Payments changes when you add a new payment provider. Different reasons to change suggest different contexts.

4. **Could this be replaced independently?** Could you swap out the notification system without touching the ticketing system? If yes, they are separate contexts.

### 🤔 Exercise: Validate the Boundaries

For each bounded context, answer: what would happen if you removed it from TicketPulse?

| Context | If Removed | Impact |
|---------|-----------|--------|
| Event Management | Cannot create or edit events | Fatal — no product |
| Ticketing | Cannot buy tickets | Fatal — no revenue |
| Payments | Cannot process money | Fatal — no revenue |
| Users | Cannot log in | Severe — but anonymous purchasing possible |
| Notifications | Cannot send emails | Degraded — purchases still work, users just do not get confirmation |

This tells you the **core domain** (Event Management + Ticketing), the **supporting domains** (Payments, Users), and the **generic domains** (Notifications). Invest the most DDD effort in the core domain.

---

## 3. Ubiquitous Language: When "Ticket" Means Three Things (10 minutes)

The most common source of bugs in large codebases is when the same word means different things in different parts of the code.

### The Problem

The word "ticket" in TicketPulse means:

| Context | What "Ticket" Means | Properties |
|---------|---------------------|-----------|
| Event Management | A sellable seat configuration | section, row, seat number, tier, face value |
| Ticketing | An inventory item that transitions through states | status (available, reserved, sold, refunded), holder, reservation expiry |
| Payments | A line item on an order | amount, tax, service fee, discount applied |
| Notifications | A delivery target | recipient email, ticket ID, QR code URL, event details for the email template |

If you have a single `Ticket` class used everywhere, it accumulates properties from all four contexts. It becomes a God Object with 30 fields, half of which are irrelevant in any given context.

### The Fix: One Model Per Context

```typescript
// Event Management context: a ticket configuration
interface EventTicketConfig {
  section: string;
  row: string;
  seatNumber: number;
  tier: 'general' | 'vip' | 'premium';
  faceValueInCents: number;
}

// Ticketing context: an inventory item
interface TicketInventoryItem {
  id: string;
  eventId: string;
  status: 'available' | 'reserved' | 'sold' | 'refunded';
  holderId?: string;
  reservedUntil?: Date;
}

// Payments context: a line item
interface OrderLineItem {
  ticketId: string;
  description: string;         // "VIP - Row A, Seat 12"
  amountInCents: number;
  serviceFeeInCents: number;
  discountAppliedInCents: number;
}

// Notifications context: delivery details
interface TicketNotificationPayload {
  recipientEmail: string;
  ticketId: string;
  eventTitle: string;
  eventDate: string;
  venue: string;
  qrCodeUrl: string;
}
```

Four different types, all called "ticket" in conversation, but each with only the properties relevant to its context. No God Object. No confusion.

### 🤔 Reflect

Look at your current TicketPulse code. Is there a single `Ticket` type or interface? How many properties does it have? How many of those properties are only used in one place?

---

## 4. Context Map: How Contexts Communicate (10 minutes)

Bounded contexts are not isolated islands. They communicate. The **context map** shows how.

### 📐 Design: TicketPulse Context Map

<details>
<summary>💡 Hint 1: Follow the data flow from event creation to email</summary>
Start with Event Management (upstream). Ticketing consumes event data to create inventory. Payments processes charges based on orders from Ticketing. Notifications is downstream of everything — it reacts to events from all other contexts.
</details>

<details>
<summary>💡 Hint 2: Identify sync vs async communication</summary>
Ticketing calls Event Management synchronously (it needs event details before creating inventory). But Ticketing communicates with Notifications asynchronously via domain events like `TicketPurchased`. The direction of the arrow and whether it is sync or async matters for coupling.
</details>

<details>
<summary>💡 Hint 3: Label the relationship patterns</summary>
Event Management is the "supplier" to Ticketing's "customer." Notifications is a "conformist" — it adapts to whatever data the other contexts provide. If you integrate with Stripe, the Payments context wraps Stripe's API in an Anti-Corruption Layer so Stripe's model does not leak into your domain.
</details>


```
  ┌─────────────────┐         ┌─────────────────┐
  │     Event        │         │    Ticketing     │
  │   Management     │────────→│                  │
  │                  │ provides │  Consumes event  │
  │  (Upstream)      │ event   │  data to create  │
  │                  │ details │  inventory        │
  └────────┬─────────┘         └────────┬─────────┘
           │                            │
           │                            │ emits
           │                            │ TicketPurchased
           │                            ▼
           │                   ┌─────────────────┐
           │                   │    Payments      │
           │                   │                  │
           │                   │  Processes       │
           │                   │  charges based   │
           │                   │  on order        │
           │                   └────────┬─────────┘
           │                            │
           │                            │ emits
           │                            │ PaymentCompleted
           │                            ▼
           │                   ┌─────────────────┐
           │                   │  Notifications   │
           │                   │                  │
           │                   │  Sends email     │
           │                   │  confirmations   │
           │                   │                  │
           └──────────────────→│  (Downstream of  │
             provides event    │   everything)    │
             details for       └─────────────────┘
             email templates
```

### Communication Patterns Between Contexts

| From | To | Pattern | Example |
|------|----|---------|---------|
| Event Management | Ticketing | Synchronous API call | Ticketing calls `events.getEventById()` to validate event exists before creating inventory |
| Ticketing | Payments | Synchronous API call | Purchase flow calls `payments.processCharge()` and waits for result |
| Payments | Ticketing | Domain event | `PaymentCompleted` event triggers ticket status change from "reserved" to "sold" |
| Ticketing | Notifications | Domain event (async) | `TicketPurchased` event triggers email confirmation |
| Event Management | Notifications | Data lookup | Notifications fetches event details for email templates |

### Context Mapping Patterns

The relationship between contexts matters:

**Customer-Supplier:** Ticketing (customer) depends on Event Management (supplier). Event Management provides what Ticketing needs. If Event Management changes its API, Ticketing must adapt.

**Conformist:** Notifications conforms to whatever data the other contexts provide. It does not ask for changes — it takes what it gets and builds email templates from it.

**Anti-Corruption Layer:** If TicketPulse integrates with an external payment provider (Stripe), the Payments context wraps Stripe's API in an Anti-Corruption Layer so Stripe's data model does not leak into TicketPulse's domain.

```typescript
// Anti-Corruption Layer: translate Stripe's model to our domain
class StripePaymentAdapter implements PaymentGateway {
  async processCharge(order: Order): Promise<PaymentResult> {
    // Translate OUR Order into STRIPE's charge request
    const stripeCharge = {
      amount: order.totalInCents,
      currency: 'usd',
      source: order.paymentMethodToken,
      metadata: { orderId: order.id },
    };

    const result = await stripe.charges.create(stripeCharge);

    // Translate STRIPE's response back to OUR domain
    return {
      id: result.id,
      status: result.status === 'succeeded' ? 'completed' : 'failed',
      amountInCents: result.amount,
      processedAt: new Date(result.created * 1000),
    };
  }
}
```

Stripe's data model (with its own conventions, field names, and structures) never leaks past this adapter. The rest of TicketPulse only sees `PaymentResult`.

---

## 5. Aggregates: The Order as a Consistency Boundary (15 minutes)

An **aggregate** is a cluster of domain objects that are treated as a single unit for data changes. The **aggregate root** is the entry point — all modifications go through it.

### Why Aggregates Matter

Without aggregates, any code can modify any data:

```typescript
// BAD: Directly modifying order lines from anywhere
orderLine.quantity = 5;
orderLine.priceInCents = 0; // Oops, free tickets!
// Nothing enforces that totalInCents is recalculated
// Nothing enforces that inventory is checked
```

With aggregates, all modifications go through the root, which enforces business rules (invariants):

```typescript
// GOOD: All modifications through the aggregate root
order.addTicket(eventId, tier, quantity);
// The Order aggregate internally:
// 1. Checks inventory
// 2. Calculates price
// 3. Updates total
// 4. Enforces max 10 tickets per order
```

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Build: Order Aggregate

<details>
<summary>💡 Hint 1: Start with invariants, not data</summary>
List the business rules first: max 10 tickets per order, no duplicate event+tier combos, cannot modify a paid order, cannot confirm an empty order. These invariants become guard clauses inside the aggregate's methods — they are what make the aggregate more than a data container.
</details>

<details>
<summary>💡 Hint 2: Use Value Objects for Money</summary>
Create a `Money` class that wraps `amountInCents: number`. Enforce non-negative values in the constructor. Give it an `add()` method. This prevents accidental arithmetic on raw numbers (like adding cents to dollars) and makes the Order's `total` calculation self-documenting.
</details>

<details>
<summary>💡 Hint 3: Emit domain events on state transitions</summary>
When the Order moves from `draft` to `confirmed`, push an `OrderConfirmed` event into an internal `events: DomainEvent[]` array. Expose a `pullEvents()` method that returns and clears the array. The application layer calls `pullEvents()` after saving and publishes them to the event bus from M21.
</details>


```typescript
// src/modules/ticketing/domain/order.ts

import { calculateTicketPrice, PricingInput } from '../../shared/pricing';

// ---- Value Objects ----

class Money {
  constructor(public readonly amountInCents: number) {
    if (amountInCents < 0) throw new Error('Money cannot be negative');
    if (!Number.isInteger(amountInCents)) throw new Error('Money must be in whole cents');
  }

  add(other: Money): Money {
    return new Money(this.amountInCents + other.amountInCents);
  }

  equals(other: Money): boolean {
    return this.amountInCents === other.amountInCents;
  }
}

class OrderLineId {
  constructor(public readonly value: string) {}
}

// ---- Entities ----

class OrderLine {
  constructor(
    public readonly id: OrderLineId,
    public readonly eventId: string,
    public readonly eventTitle: string,
    public readonly tier: 'general' | 'vip' | 'early_bird',
    public readonly quantity: number,
    public readonly unitPrice: Money,
    public readonly serviceFee: Money,
  ) {}

  get subtotal(): Money {
    return new Money(this.unitPrice.amountInCents * this.quantity);
  }

  get totalWithFees(): Money {
    return this.subtotal.add(this.serviceFee);
  }
}

// ---- Domain Events ----

interface DomainEvent {
  type: string;
  occurredAt: Date;
  payload: Record<string, unknown>;
}

// ---- Aggregate Root ----

type OrderStatus = 'draft' | 'confirmed' | 'paid' | 'cancelled' | 'refunded';

export class Order {
  private lines: OrderLine[] = [];
  private _status: OrderStatus = 'draft';
  private events: DomainEvent[] = [];

  constructor(
    public readonly id: string,
    public readonly customerId: string,
    public readonly createdAt: Date = new Date(),
  ) {}

  // ---- Commands (things you can do to an Order) ----

  addTicket(
    eventId: string,
    eventTitle: string,
    tier: 'general' | 'vip' | 'early_bird',
    quantity: number,
    basePriceInCents: number,
    eventDate: Date,
  ): void {
    // Invariant: can only modify draft orders
    this.assertStatus('draft', 'add tickets to');

    // Invariant: max 10 tickets per order
    const currentTotal = this.totalTicketCount;
    if (currentTotal + quantity > 10) {
      throw new Error(
        `Cannot add ${quantity} tickets. Order already has ${currentTotal}. Maximum is 10.`
      );
    }

    // Invariant: no duplicate events in same order (simplification)
    if (this.lines.some(line => line.eventId === eventId && line.tier === tier)) {
      throw new Error(`Order already contains ${tier} tickets for this event`);
    }

    // Calculate price through the pricing service
    const pricing = calculateTicketPrice({
      basePriceInCents,
      tier,
      quantity,
      eventDate,
    });

    const line = new OrderLine(
      new OrderLineId(`${this.id}-${this.lines.length + 1}`),
      eventId,
      eventTitle,
      tier,
      quantity,
      new Money(pricing.unitPriceInCents),
      new Money(pricing.serviceFeeInCents),
    );

    this.lines.push(line);
  }

  removeTicket(lineId: string): void {
    this.assertStatus('draft', 'remove tickets from');

    const index = this.lines.findIndex(l => l.id.value === lineId);
    if (index === -1) throw new Error(`Order line ${lineId} not found`);

    this.lines.splice(index, 1);
  }

  confirm(): void {
    this.assertStatus('draft', 'confirm');

    if (this.lines.length === 0) {
      throw new Error('Cannot confirm an empty order');
    }

    this._status = 'confirmed';

    this.events.push({
      type: 'OrderConfirmed',
      occurredAt: new Date(),
      payload: {
        orderId: this.id,
        customerId: this.customerId,
        totalInCents: this.total.amountInCents,
        lineCount: this.lines.length,
      },
    });
  }

  markPaid(paymentId: string): void {
    this.assertStatus('confirmed', 'mark as paid');

    this._status = 'paid';

    this.events.push({
      type: 'OrderPaid',
      occurredAt: new Date(),
      payload: {
        orderId: this.id,
        customerId: this.customerId,
        paymentId,
        totalInCents: this.total.amountInCents,
      },
    });
  }

  cancel(reason: string): void {
    if (this._status === 'cancelled' || this._status === 'refunded') {
      throw new Error(`Cannot cancel an order that is already ${this._status}`);
    }

    this._status = 'cancelled';

    this.events.push({
      type: 'OrderCancelled',
      occurredAt: new Date(),
      payload: {
        orderId: this.id,
        customerId: this.customerId,
        reason,
      },
    });
  }

  // ---- Queries (read the Order's state) ----

  get status(): OrderStatus {
    return this._status;
  }

  get orderLines(): readonly OrderLine[] {
    return [...this.lines]; // Return a copy — external code cannot mutate
  }

  get totalTicketCount(): number {
    return this.lines.reduce((sum, line) => sum + line.quantity, 0);
  }

  get subtotal(): Money {
    return this.lines.reduce(
      (sum, line) => sum.add(line.subtotal),
      new Money(0)
    );
  }

  get totalServiceFees(): Money {
    return this.lines.reduce(
      (sum, line) => sum.add(line.serviceFee),
      new Money(0)
    );
  }

  get total(): Money {
    return this.subtotal.add(this.totalServiceFees);
  }

  // ---- Domain Events ----

  pullEvents(): DomainEvent[] {
    const pulled = [...this.events];
    this.events = [];
    return pulled;
  }

  // ---- Private helpers ----

  private assertStatus(expected: OrderStatus, action: string): void {
    if (this._status !== expected) {
      throw new Error(
        `Cannot ${action} an order with status "${this._status}". Expected "${expected}".`
      );
    }
  }
}
```

### What This Enforces

The Order aggregate guarantees these **invariants** (business rules that must always be true):

1. **Maximum 10 tickets per order.** Enforced in `addTicket()`. External code cannot bypass this.
2. **No duplicate event+tier combinations.** Enforced in `addTicket()`.
3. **Status transitions are valid.** Cannot mark a draft order as paid (must confirm first). Cannot confirm an empty order.
4. **Order lines are immutable from outside.** `orderLines` returns a copy. External code cannot mutate the internal array.
5. **Pricing is calculated consistently.** `addTicket()` uses the pricing service. External code cannot set arbitrary prices.
6. **Domain events are emitted on state changes.** `OrderConfirmed`, `OrderPaid`, `OrderCancelled` are recorded for downstream consumers.

### 🔍 Try It: The Invariants in Action

```typescript
// This works:
const order = new Order('ord-1', 'user-123');
order.addTicket('evt-1', 'Taylor Swift', 'vip', 2, 15000, futureDate);
order.confirm();
order.markPaid('pay-abc');

// These throw errors:
order.addTicket('evt-1', 'Taylor Swift', 'vip', 2, 15000, futureDate);
// Error: Order already contains vip tickets for this event

const bigOrder = new Order('ord-2', 'user-456');
bigOrder.addTicket('evt-1', 'Event', 'general', 8, 5000, futureDate);
bigOrder.addTicket('evt-2', 'Other', 'general', 5, 5000, futureDate);
// Error: Cannot add 5 tickets. Order already has 8. Maximum is 10.

const emptyOrder = new Order('ord-3', 'user-789');
emptyOrder.confirm();
// Error: Cannot confirm an empty order

order.addTicket('evt-3', 'More', 'general', 1, 5000, futureDate);
// Error: Cannot add tickets to an order with status "paid". Expected "draft".
```

### ⚠️ Common Mistake: Aggregates That Are Too Big

An aggregate should be the smallest group of objects that must be consistent together. An Order with its OrderLines is a good aggregate — they must always be consistent (total must match lines).

But do NOT put the Event inside the Order aggregate. An Event has its own lifecycle, its own invariants, and its own transactions. If the Order aggregate included the Event, you would lock the Event row every time someone modifies their order.

**Rule of thumb:** One aggregate = one transaction. If two things do not need to change in the same transaction, they should be separate aggregates.

---

## 6. Where to Apply DDD (and Where Not To) (5 minutes)

### The Core Domain Gets Full DDD

TicketPulse's core domain is Ticketing + Event Management. This is where the money is. This is where the complex business logic lives. This is where DDD aggregates, value objects, and domain events pay off.

### Supporting Domains Get Lighter Treatment

Payments and Users have important business logic, but they are not unique to TicketPulse. Every e-commerce app has payments and users. Apply DDD selectively — maybe aggregates for complex payment flows, but simple CRUD for user profiles.

### Generic Domains Get Minimal DDD

Notifications is a generic subdomain. Sending emails is not TicketPulse's competitive advantage. Use a simple service class. Do not over-engineer it with aggregates and domain events. A function that takes an email address and a template is fine.

### 🤔 Reflect: Where Are the Natural Seams?

If you HAD to split TicketPulse into exactly two services, where would you cut?

The most natural split: **Commerce (Ticketing + Payments)** and **Catalog (Event Management + Users + Notifications).**

Commerce is the transactional core — it handles money and inventory and needs strong consistency. Catalog is the read-heavy discovery layer — it handles browsing, search, and communication and can tolerate eventual consistency.

This maps directly to the bounded contexts and their consistency requirements from M18.

---

## 7. Checkpoint

After this module, you should have:

- [ ] Identified TicketPulse's five bounded contexts
- [ ] Drawn a context map showing how contexts communicate
- [ ] Understood ubiquitous language — why "ticket" means different things in different contexts
- [ ] Built the Order aggregate with invariant enforcement
- [ ] Understood the relationship between aggregates and transactions
- [ ] Classified TicketPulse's domains (core, supporting, generic)
- [ ] Identified where DDD pays off and where it is overkill

**Key takeaway: DDD is about finding the right boundaries. The tactical patterns (aggregates, value objects) are tools for enforcing those boundaries in code.**

---

## Glossary

| Term | Definition |
|------|-----------|
| **Domain** | The business problem the software solves. TicketPulse's domain is live event ticketing. |
| **Bounded context** | A boundary within which a particular domain model is defined and consistent. Each context has its own ubiquitous language. |
| **Ubiquitous language** | The shared vocabulary used by developers and domain experts within a bounded context. Used in code and conversation. |
| **Context map** | A diagram showing how bounded contexts relate to and communicate with each other. |
| **Aggregate** | A cluster of domain objects treated as a single unit. All changes go through the aggregate root. One aggregate = one transaction. |
| **Aggregate root** | The entry point to an aggregate. External code can only modify the aggregate through the root. |
| **Value object** | An object defined by its attributes (not its identity). Immutable. Two value objects with the same attributes are equal. `Money(100)` equals `Money(100)`. |
| **Entity** | An object defined by its identity. Two entities with the same attributes but different IDs are different. Two users named "Alice" are different users. |
| **Domain event** | A record of something significant that happened in the domain. Past tense: `OrderConfirmed`, `TicketPurchased`. |
| **Core domain** | The part of the domain that is the business's competitive advantage. Deserves the most investment in modeling. |
| **Anti-Corruption Layer** | A translation layer that prevents an external system's model from leaking into your domain. |

---

## Further Reading

- Eric Evans, *Domain-Driven Design*, Chapters 1-5 (Strategic Design)
- Vaughn Vernon, *Implementing Domain-Driven Design*, Chapter 10 (Aggregates)
- [Martin Fowler on Bounded Contexts](https://martinfowler.com/bliki/BoundedContext.html)
- Chapter 3 of the 100x Engineer Guide: Section 4 (Domain-Driven Design)
---

## What's Next

In **Event-Driven Thinking** (L1-M21), you'll build on what you learned here and take it further.
