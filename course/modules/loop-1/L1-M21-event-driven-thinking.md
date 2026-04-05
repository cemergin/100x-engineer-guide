# L1-M21: Event-Driven Thinking

> **Loop 1 (Foundation)** | Section 1D: Architecture Fundamentals | ⏱️ 60 min | 🟢 Core | Prerequisites: L1-M20 (Domain-Driven Design Basics)
>
> **Source:** Chapters 1, 3 of the 100x Engineer Guide

---

## The Goal

A user buys a ticket. What happens next?

Right now in TicketPulse, the purchase endpoint does everything inline: reserve the ticket, charge the payment, send a confirmation email, update analytics, generate a receipt. All of this happens before the user gets a response.

If the email service takes 2 seconds, the user waits 2 seconds. If the analytics service is down, the purchase fails — even though the payment already went through.

This is wrong. The email can be sent later. The analytics can be updated later. The only thing the user needs to see immediately is "your ticket is confirmed."

In this module, you will think about what should happen synchronously (before the response) and what should happen asynchronously (after the response). You will build a simple event system to decouple these concerns. And you will feel the performance difference.

**You will see API response times spike within the first ten minutes.**

---

## 1. The Side Effects of a Ticket Purchase (10 minutes)

### 🤔 Exercise: List Everything That Happens

A user clicks "Buy Ticket." Before they see a confirmation page, what ELSE should happen besides reserving the ticket?

Write your list before reading further.

---

Here is a realistic list:

| Side Effect | Description |
|------------|-------------|
| Reserve inventory | Decrement available tickets, mark seat as sold |
| Process payment | Charge the customer's credit card |
| Create order record | Write the order to the database |
| Send confirmation email | Email with ticket details and QR code |
| Send push notification | "You got tickets!" notification on mobile |
| Update analytics | Increment purchase count, revenue metrics |
| Generate PDF ticket | Create a downloadable/printable ticket |
| Generate receipt | Create a tax receipt for the purchase |
| Update search index | Mark event as "selling fast" or "sold out" |
| Notify event organizer | "You just sold 2 tickets!" dashboard update |
| Trigger fraud check | Async review of purchase for suspicious patterns |
| Update recommendation engine | "Users who bought X also bought Y" |

That is 12 side effects. How many of these must happen before the user sees "Purchase confirmed"?

### The Key Question: Synchronous or Async?

| Side Effect | Must Be Sync? | Why |
|------------|---------------|-----|
| Reserve inventory | YES | Cannot sell the same ticket twice |
| Process payment | YES | Must confirm money was charged |
| Create order record | YES | Must persist the purchase |
| Send confirmation email | No | Can arrive 30 seconds later |
| Send push notification | No | Can arrive 30 seconds later |
| Update analytics | No | Can happen minutes later |
| Generate PDF ticket | No | Can be generated on demand or async |
| Generate receipt | No | Can be generated on demand |
| Update search index | No | A few seconds of staleness is fine |
| Notify event organizer | No | Real-time is nice, not critical |
| Trigger fraud check | No | Happens after the fact by definition |
| Update recommendations | No | Can happen in batch overnight |

**Only 3 of 12 side effects need to be synchronous.** The other 9 can happen later. But if you do all 12 synchronously, the user waits for all of them.

---

## 2. The Cost of Synchronous Side Effects (10 minutes)

### 🔍 Try It: Feel the Pain

Let us add a slow side effect to the purchase flow and measure the impact.

```typescript
// src/routes/tickets.ts — current synchronous approach

async function purchaseTicket(req: Request, res: Response) {
  const startTime = Date.now();

  // Step 1: Reserve inventory (fast, ~5ms)
  const ticket = await reserveTicket(req.params.eventId, req.body.email);

  // Step 2: Process payment (moderate, ~200ms)
  const payment = await processPayment(ticket, req.body.paymentMethod);

  // Step 3: Create order (fast, ~5ms)
  const order = await createOrder(ticket, payment);

  // Step 4: Send confirmation email (SLOW, ~2000ms)
  await sendConfirmationEmail(req.body.email, order);

  // Step 5: Update analytics (moderate, ~100ms)
  await updateAnalytics('ticket_purchased', { eventId: req.params.eventId });

  // Step 6: Generate PDF ticket (SLOW, ~1500ms)
  await generatePdfTicket(order);

  const totalTime = Date.now() - startTime;
  console.log(`[purchase] Total time: ${totalTime}ms`);

  return res.status(201).json({ data: order });
}
```

Simulate the slow services:

```typescript
// Simulated slow services (for demonstration)
async function sendConfirmationEmail(email: string, order: any): Promise<void> {
  // Simulates calling SendGrid API
  await new Promise(resolve => setTimeout(resolve, 2000));
  console.log(`[email] Sent confirmation to ${email}`);
}

async function updateAnalytics(event: string, data: any): Promise<void> {
  // Simulates sending to analytics service
  await new Promise(resolve => setTimeout(resolve, 100));
  console.log(`[analytics] Recorded ${event}`);
}

async function generatePdfTicket(order: any): Promise<void> {
  // Simulates PDF generation
  await new Promise(resolve => setTimeout(resolve, 1500));
  console.log(`[pdf] Generated ticket for order ${order.id}`);
}
```

### 🔍 Try It: Measure the Response Time

```bash
# Time the purchase request
time curl -s -X POST http://localhost:3000/api/events/1/tickets \
  -H 'Content-Type: application/json' \
  -d '{"email": "buyer@example.com", "paymentMethod": "tok_visa"}'
```

Expected output:

```
[purchase] Total time: 3810ms
  - reserveTicket: 5ms
  - processPayment: 200ms
  - createOrder: 5ms
  - sendConfirmationEmail: 2000ms  ← User is waiting for this!
  - updateAnalytics: 100ms         ← And this!
  - generatePdfTicket: 1500ms      ← And this!

real    0m3.850s
```

The user waited **3.8 seconds** to see their confirmation. But the purchase was done after 210ms. The remaining 3.6 seconds were spent on things the user does not need to see before the response.

---

## 3. Build: In-Process Event Emitter (15 minutes)

### The Pattern: Emit Events, React Later

Instead of calling side effects directly, the purchase endpoint will emit a domain event. Listeners will react to the event independently.

```
Purchase Flow                    Event Bus                    Listeners
┌──────────────┐                ┌──────────┐
│ Reserve      │                │          │
│ Process pay  │                │ Ticket   │───→ [sendConfirmationEmail]
│ Create order │──emit──────────│ Purchased│───→ [updateAnalytics]
│              │                │          │───→ [generatePdfTicket]
│ Return 201   │ (does not      │          │───→ [notifyOrganizer]
│              │  wait for      └──────────┘
└──────────────┘  listeners)
```

> **Before you continue:** Take a moment to think about how you would approach this before reading the solution. What's your instinct?

### 🛠️ Build: The Event Emitter

<details>
<summary>💡 Hint 1: Direction</summary>
Think about the overall approach before diving into implementation details.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Break the problem into smaller steps. What needs to happen first?
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Review the concepts from this section. The solution follows the same patterns demonstrated above.
</details>


```typescript
// src/events/eventBus.ts

type EventHandler = (payload: any) => void | Promise<void>;

class EventBus {
  private handlers: Map<string, EventHandler[]> = new Map();
  private asyncHandlers: Map<string, EventHandler[]> = new Map();

  /**
   * Register a synchronous listener.
   * The emitter WAITS for this handler to complete.
   * Use for critical side effects (inventory, payment).
   */
  onSync(eventType: string, handler: EventHandler): void {
    const existing = this.handlers.get(eventType) || [];
    existing.push(handler);
    this.handlers.set(eventType, existing);
  }

  /**
   * Register an asynchronous listener.
   * The emitter does NOT wait for this handler.
   * Use for non-critical side effects (email, analytics).
   */
  onAsync(eventType: string, handler: EventHandler): void {
    const existing = this.asyncHandlers.get(eventType) || [];
    existing.push(handler);
    this.asyncHandlers.set(eventType, existing);
  }

  /**
   * Emit an event.
   * - Synchronous handlers execute and are awaited.
   * - Asynchronous handlers fire and are NOT awaited.
   */
  async emit(eventType: string, payload: any): Promise<void> {
    console.log(`[event-bus] Emitting: ${eventType}`);

    // Run synchronous handlers (wait for them)
    const syncHandlers = this.handlers.get(eventType) || [];
    for (const handler of syncHandlers) {
      await handler(payload);
    }

    // Fire asynchronous handlers (do NOT wait)
    const asyncHandlers = this.asyncHandlers.get(eventType) || [];
    for (const handler of asyncHandlers) {
      handler(payload).catch(err => {
        console.error(`[event-bus] Async handler failed for ${eventType}:`, err.message);
        // Log the error but do not crash. The purchase already succeeded.
      });
    }
  }

  /**
   * List all registered handlers (for debugging).
   */
  listHandlers(): Record<string, { sync: number; async: number }> {
    const result: Record<string, { sync: number; async: number }> = {};
    const allTypes = new Set([
      ...this.handlers.keys(),
      ...this.asyncHandlers.keys(),
    ]);
    for (const type of allTypes) {
      result[type] = {
        sync: this.handlers.get(type)?.length || 0,
        async: this.asyncHandlers.get(type)?.length || 0,
      };
    }
    return result;
  }
}

// Singleton — one event bus for the whole application
export const eventBus = new EventBus();
```

### Define Domain Events

```typescript
// src/events/domainEvents.ts

export interface TicketPurchasedEvent {
  type: 'TicketPurchased';
  occurredAt: Date;
  payload: {
    orderId: string;
    ticketId: string;
    eventId: string;
    eventTitle: string;
    customerEmail: string;
    amountInCents: number;
    tier: string;
  };
}

export interface EventCreatedEvent {
  type: 'EventCreated';
  occurredAt: Date;
  payload: {
    eventId: string;
    title: string;
    venue: string;
    date: string;
    totalTickets: number;
  };
}

export interface PaymentProcessedEvent {
  type: 'PaymentProcessed';
  occurredAt: Date;
  payload: {
    paymentId: string;
    orderId: string;
    amountInCents: number;
    status: 'succeeded' | 'failed';
  };
}

export interface UserRegisteredEvent {
  type: 'UserRegistered';
  occurredAt: Date;
  payload: {
    userId: string;
    email: string;
    name: string;
  };
}
```

### Register Listeners

```typescript
// src/events/listeners.ts

import { eventBus } from './eventBus';

// ---- Logging (synchronous — always runs) ----
eventBus.onSync('TicketPurchased', (event) => {
  console.log(
    `[log] Ticket purchased: order=${event.payload.orderId}, ` +
    `event=${event.payload.eventTitle}, ` +
    `amount=$${(event.payload.amountInCents / 100).toFixed(2)}`
  );
});

// ---- Email confirmation (asynchronous — does not block the response) ----
eventBus.onAsync('TicketPurchased', async (event) => {
  const { customerEmail, eventTitle, orderId } = event.payload;
  console.log(`[email] Sending confirmation to ${customerEmail}...`);

  // Simulate slow email API
  await new Promise(resolve => setTimeout(resolve, 2000));

  console.log(`[email] Confirmation sent to ${customerEmail} for ${eventTitle}`);
});

// ---- Analytics (asynchronous) ----
eventBus.onAsync('TicketPurchased', async (event) => {
  console.log(`[analytics] Recording purchase for event ${event.payload.eventId}...`);

  // Simulate analytics API call
  await new Promise(resolve => setTimeout(resolve, 100));

  console.log(`[analytics] Purchase recorded`);
});

// ---- PDF generation (asynchronous) ----
eventBus.onAsync('TicketPurchased', async (event) => {
  console.log(`[pdf] Generating ticket PDF for order ${event.payload.orderId}...`);

  // Simulate PDF generation
  await new Promise(resolve => setTimeout(resolve, 1500));

  console.log(`[pdf] Ticket PDF generated for order ${event.payload.orderId}`);
});

// ---- Event Created listeners ----
eventBus.onAsync('EventCreated', async (event) => {
  console.log(`[search] Indexing new event: ${event.payload.title}`);
  await new Promise(resolve => setTimeout(resolve, 200));
  console.log(`[search] Event indexed`);
});

// ---- User Registered listeners ----
eventBus.onAsync('UserRegistered', async (event) => {
  console.log(`[email] Sending welcome email to ${event.payload.email}`);
  await new Promise(resolve => setTimeout(resolve, 1000));
  console.log(`[email] Welcome email sent`);
});
```

### Update the Purchase Endpoint

```typescript
// src/routes/tickets.ts — event-driven approach

import { eventBus } from '../events/eventBus';

async function purchaseTicket(req: Request, res: Response) {
  const startTime = Date.now();

  // Step 1: Reserve inventory (SYNC — must happen before response)
  const ticket = await reserveTicket(req.params.eventId, req.body.email);

  // Step 2: Process payment (SYNC — must happen before response)
  const payment = await processPayment(ticket, req.body.paymentMethod);

  // Step 3: Create order (SYNC — must happen before response)
  const order = await createOrder(ticket, payment);

  // Step 4: Emit domain event (listeners handle everything else)
  await eventBus.emit('TicketPurchased', {
    type: 'TicketPurchased',
    occurredAt: new Date(),
    payload: {
      orderId: order.id,
      ticketId: ticket.id,
      eventId: req.params.eventId,
      eventTitle: ticket.eventTitle,
      customerEmail: req.body.email,
      amountInCents: order.totalInCents,
      tier: req.body.tier || 'general',
    },
  });

  const totalTime = Date.now() - startTime;
  console.log(`[purchase] Response sent in ${totalTime}ms`);

  // Response returns IMMEDIATELY after sync handlers finish
  // Async handlers (email, PDF, analytics) continue in the background
  return res.status(201).json({ data: order });
}
```

### 🔍 Try It: Feel the Difference

```bash
# Time the purchase with event-driven approach
time curl -s -X POST http://localhost:3000/api/events/1/tickets \
  -H 'Content-Type: application/json' \
  -d '{"email": "buyer@example.com", "paymentMethod": "tok_visa"}'
```

Expected output:

```
[purchase] Response sent in 215ms    ← User sees this immediately!
[log] Ticket purchased: order=ord-123, event=Taylor Swift, amount=$150.00
[email] Sending confirmation to buyer@example.com...
[analytics] Recording purchase for event evt-1...
[pdf] Generating ticket PDF for order ord-123...
[analytics] Purchase recorded                    ← Finishes in background
[pdf] Ticket PDF generated for order ord-123     ← Finishes in background
[email] Confirmation sent to buyer@example.com   ← Finishes in background

real    0m0.250s
```

**215ms instead of 3,810ms.** The user gets their confirmation 18x faster. The email, PDF, and analytics still happen — just in the background.

---

## 4. What Happens When a Listener Fails? (5 minutes)

### 🐛 Debug: Simulate a Listener Failure

<details>
<summary>💡 Hint 1: Direction</summary>
Think about the overall approach before diving into implementation details.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Break the problem into smaller steps. What needs to happen first?
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Review the concepts from this section. The solution follows the same patterns demonstrated above.
</details>


Add a failing listener:

```typescript
// Simulate a broken analytics service
eventBus.onAsync('TicketPurchased', async (event) => {
  console.log(`[analytics-v2] Sending to new analytics platform...`);
  throw new Error('Analytics service is down!');
});
```

Now purchase a ticket:

```bash
curl -s -X POST http://localhost:3000/api/events/1/tickets \
  -H 'Content-Type: application/json' \
  -d '{"email": "buyer@example.com", "paymentMethod": "tok_visa"}'
```

What happens:

```
[purchase] Response sent in 218ms                 ← User still gets fast response!
[log] Ticket purchased: order=ord-124, ...
[email] Sending confirmation to buyer@example.com...
[analytics-v2] Sending to new analytics platform...
[event-bus] Async handler failed for TicketPurchased: Analytics service is down!
[email] Confirmation sent to buyer@example.com
```

The purchase succeeded. The user got their confirmation. One analytics listener failed, and the error was logged. The failure is isolated — it does not affect the purchase or other listeners.

But there is a problem: **the analytics event was lost.** Nobody will retry it. If the analytics service comes back in 5 minutes, it missed this purchase.

This is the limitation of an in-process event emitter. Events live in memory. If a listener fails, the event is gone. If the process crashes, all pending async work is lost.

> **Pro tip:** This Is Why Message Queues Exist

An in-process event emitter is a stepping stone. It decouples the code, but it does not decouple the process. For real durability:
- Events should be persisted (so they survive process crashes)
- Failed events should be retried (so transient failures are handled)
- Events should be processed by separate workers (so a slow listener does not consume the API server's resources)

That is what a message queue provides. We will add one in the next module (M22).

---

## 5. When Events Are Wrong (5 minutes)

Not everything should be an event. Events add indirection. Indirection makes code harder to follow and debug.

### Use Events When

- The producer does not care who consumes the event (loose coupling)
- Multiple consumers need to react to the same action
- The reaction can happen asynchronously
- You want to add new reactions without modifying the producer

### Do NOT Use Events When

- The producer needs the result of the reaction (use a direct function call)
- There is exactly one consumer and it is tightly coupled (just call the function)
- Ordering matters and is complex (events can arrive out of order)
- The domain is simple CRUD (events add unnecessary complexity)

### TicketPulse Example

Good use of events:
```
TicketPurchased → [sendEmail, updateAnalytics, generatePdf, notifyOrganizer]
```
The purchase does not care about any of these. New listeners can be added without touching the purchase code.

Bad use of events:
```
GetEventDetails → [fetchFromDatabase] → return to caller
```
This is a simple query. There is one "consumer" (the caller). Using events here adds indirection for no benefit.

---

## 6. Reflect (5 minutes)

### 🤔 Exercise: Audit Your Purchase Flow

Look at TicketPulse's current purchase flow. For each side effect:

1. Is it currently synchronous or asynchronous?
2. Should it be synchronous or asynchronous?
3. What happens if it fails — should the purchase fail too?

| Side Effect | Currently | Should Be | If It Fails |
|------------|-----------|-----------|-------------|
| Reserve inventory | Sync | Sync | Purchase fails (correct) |
| Process payment | Sync | Sync | Purchase fails (correct) |
| Send email | ? | Async | Log error, retry later |
| Update analytics | ? | Async | Log error, ignore |
| Generate PDF | ? | Async | Generate on demand later |

### 🤔 What Other Events Should TicketPulse Emit?

Think beyond purchases:

| Event | Triggered By | Possible Listeners |
|-------|-------------|-------------------|
| `EventCreated` | Admin creates event | Index in search, notify subscribers |
| `EventUpdated` | Admin edits event | Update search index, invalidate cache |
| `EventCancelled` | Admin cancels event | Notify ticket holders, process refunds |
| `UserRegistered` | New user signs up | Send welcome email, create preferences |
| `RefundRequested` | User requests refund | Process refund, send confirmation |
| `EventSoldOut` | Last ticket purchased | Update listing, notify waitlist |

Each of these follows the same pattern: one producer, multiple consumers, most consumers are asynchronous.

---

## 7. Checkpoint

After this module, TicketPulse should have:

- [ ] An `EventBus` with support for synchronous and asynchronous listeners
- [ ] Domain events defined: `TicketPurchased`, `EventCreated`, `PaymentProcessed`, `UserRegistered`
- [ ] Listeners registered for logging, email, analytics, and PDF generation
- [ ] Purchase endpoint that emits events instead of calling side effects directly
- [ ] Demonstrated 18x response time improvement (3.8s to 0.2s)
- [ ] Error isolation: a failing listener does not crash the purchase
- [ ] Understanding of when to use events vs. direct function calls

**The purchase endpoint should respond in under 300ms, with side effects running in the background.**

**Next up:** L1-M22 where we add a real message queue (RabbitMQ) so events survive process crashes and failures are retried.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Domain event** | A record of something significant that happened in the business domain. Named in past tense: `TicketPurchased`, `OrderCancelled`. |
| **Event emitter** | A component that publishes events. Listeners (subscribers) react to events without the emitter knowing about them. |
| **Synchronous listener** | A handler that must complete before the operation continues. Used for critical side effects. |
| **Asynchronous listener** | A handler that runs in the background. The operation does not wait for it. Used for non-critical side effects. |
| **Loose coupling** | Components depend on events (contracts) rather than on each other. Adding a new listener does not require changing the producer. |
| **Fire and forget** | Emit an event and move on. Do not wait for listeners. The in-process version of async messaging. |
| **Side effect** | Any observable action beyond returning a value: sending email, writing to a database, calling an external API. |
| **Indirection** | Adding a layer between the caller and the callee. Events add indirection. Indirection trades simplicity for flexibility. |

---

## Further Reading

- Martin Fowler, [Domain Events](https://martinfowler.com/eaaDev/DomainEvent.html)
- Chapter 3 of the 100x Engineer Guide: Section 5 (Event-Driven Patterns)
- Node.js built-in `EventEmitter` documentation (our EventBus is a simplified version of this pattern)
- Udi Dahan, [Domain Events Salvation](https://udidahan.com/2009/06/14/domain-events-salvation/) — The original blog post on domain events
---

## What's Next

In **Introduction to Message Queues** (L1-M22), you'll build on what you learned here and take it further.
