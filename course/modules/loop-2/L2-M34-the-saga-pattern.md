# L2-M34: The Saga Pattern

> **Loop 2 (Practice)** | Section 2A: Breaking Apart the Monolith | ⏱️ 90 min | 🟡 Deep Dive | Prerequisites: L2-M33 (Kafka Deep Dive), L2-M31 (Strangler Fig)
>
> **Source:** Chapters 3, 21, 25 of the 100x Engineer Guide

---

## The Goal

In the monolith, the ticket purchase was a single database transaction:

```sql
BEGIN;
  INSERT INTO reservations (ticket_id, user_id) VALUES (...);
  INSERT INTO payments (order_id, amount) VALUES (...);
  INSERT INTO orders (user_id, payment_id) VALUES (...);
  INSERT INTO notifications (order_id, type) VALUES (...);
COMMIT;
```

If any step failed, the entire transaction rolled back. The database guaranteed consistency. You never had a payment without a reservation or an order without a payment.

Now the services are split. The reservation is in the event service. The payment is in the payment service. The order is in the monolith. The notification is in the notification service. There is no single database to wrap a transaction around.

What happens if payment succeeds but the reservation times out? You charged the customer but they do not have a ticket. What if the order is created but the payment service returns an error after the money was already charged? The customer has an order record but no payment confirmation.

The saga pattern solves this. Instead of one big transaction, you execute a sequence of local transactions — each in its own service — with **compensating actions** that undo the work if a later step fails.

By the end of this module, you will have a saga orchestrator that coordinates the ticket purchase across services, handles every failure path, and leaves the system in a consistent state regardless of what goes wrong.

**You will see your first saga execute end-to-end within ten minutes.**

---

> **Before you continue:** In the monolith, a ticket purchase was one database transaction — if payment fails, the reservation rolls back automatically. With separate services, how would you undo a reservation after a payment failure? Think about this before reading on.


## 0. The Problem: Distributed Transactions (5 minutes)

### The Happy Path

```
Step 1: Reserve ticket     → reservation created
Step 2: Process payment    → payment charged
Step 3: Confirm order      → order created
Step 4: Send notification  → email queued
```

Every step succeeds. The customer has a ticket, the payment is recorded, the order exists, and the email is on its way.

### The Failure Paths

What if Step 2 (payment) fails?

```
Step 1: Reserve ticket     → reservation created     ← NEEDS TO BE UNDONE
Step 2: Process payment    → FAILED
```

The reservation must be released. Otherwise, a seat is held for a customer who never paid.

What if Step 3 (order creation) fails?

```
Step 1: Reserve ticket     → reservation created     ← NEEDS TO BE UNDONE
Step 2: Process payment    → payment charged          ← NEEDS TO BE REFUNDED
Step 3: Confirm order      → FAILED
```

Now you need to refund the payment AND release the reservation. The compensations must happen in reverse order.

### The Saga

A saga is a sequence of local transactions where each transaction has a corresponding **compensating action:**

| Step | Action | Compensating Action |
|------|--------|-------------------|
| 1 | Reserve ticket | Release reservation |
| 2 | Process payment | Refund payment |
| 3 | Confirm order | Cancel order |
| 4 | Send notification | (No compensation needed — notifications are best-effort) |

If step N fails, execute compensating actions for steps N-1, N-2, ..., 1 in reverse order.

---

## 1. Design: The TicketPulse Purchase Saga (10 minutes)

### 📐 Design Exercise

<details>
<summary>💡 Hint 1: Direction</summary>
Consider the trade-offs between different approaches before choosing one.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Refer back to the patterns introduced earlier in this module.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The solution uses the same technique shown in the examples above, adapted to this specific scenario.
</details>


Before writing code, design the saga. Draw the happy path and every failure path with compensating actions.

**Your saga has four steps. That means four possible failure points (plus failures during compensation itself).**

### The State Machine

```
                    ┌───────────────┐
                    │   STARTED     │
                    └───────┬───────┘
                            │
                    ┌───────▼───────┐     ┌─────────────────────┐
                    │  RESERVING    │────→│ COMPENSATION:       │
                    │  TICKET       │fail │ (nothing to undo)   │
                    └───────┬───────┘     │ → FAILED            │
                            │ ok          └─────────────────────┘
                    ┌───────▼───────┐     ┌─────────────────────┐
                    │  PROCESSING   │────→│ COMPENSATION:       │
                    │  PAYMENT      │fail │ Release reservation │
                    └───────┬───────┘     │ → FAILED            │
                            │ ok          └─────────────────────┘
                    ┌───────▼───────┐     ┌─────────────────────┐
                    │  CONFIRMING   │────→│ COMPENSATION:       │
                    │  ORDER        │fail │ Refund payment      │
                    └───────┬───────┘     │ Release reservation │
                            │ ok          │ → FAILED            │
                    ┌───────▼───────┐     └─────────────────────┘
                    │  SENDING      │
                    │  NOTIFICATION │──fail──→ (log error, continue)
                    └───────┬───────┘
                            │ ok
                    ┌───────▼───────┐
                    │  COMPLETED    │
                    └───────────────┘
```


<details>
<summary>💡 Hint 1: Direction</summary>
Draw the state machine: each step either succeeds (move forward) or fails (compensate backwards). Think about which steps are truly reversible and which are not.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
The saga has four steps: reserve ticket, process payment, confirm order, send notification. Each reversible step needs a compensating action. Compensations execute in reverse order of the completed steps.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Notification failure should NOT trigger compensation — it is best-effort. If compensation itself fails, log it and continue compensating remaining steps. Track compensation errors separately for alerting.
</details>

### 🤔 Design Questions (answer before reading on)

1. Should notification failure cause the saga to compensate? Why or why not?
2. What happens if the refund (compensating action) itself fails?
3. Should the customer see "purchase in progress" or "purchase complete" before the saga finishes?

---

## 2. Build: The Saga Orchestrator (25 minutes)

### 🛠️ Build: Saga Types and State

<details>
<summary>💡 Hint 1: Direction</summary>
Consider the trade-offs between different approaches before choosing one.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Refer back to the patterns introduced earlier in this module.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The solution uses the same technique shown in the examples above, adapted to this specific scenario.
</details>


```typescript
// src/sagas/types.ts

export type SagaStatus =
  | 'STARTED'
  | 'RESERVING_TICKET'
  | 'PROCESSING_PAYMENT'
  | 'CONFIRMING_ORDER'
  | 'SENDING_NOTIFICATION'
  | 'COMPLETED'
  | 'COMPENSATING'
  | 'FAILED';

export interface SagaStep {
  name: string;
  execute: (context: SagaContext) => Promise<void>;
  compensate: (context: SagaContext) => Promise<void>;
}

export interface SagaContext {
  sagaId: string;
  status: SagaStatus;

  // Input
  eventId: string;
  userId: string;
  email: string;
  paymentMethod: string;
  tier: string;

  // Accumulated state from each step
  reservationId?: string;
  ticketId?: string;
  paymentId?: string;
  orderId?: string;
  amountInCents?: number;

  // Error tracking
  error?: string;
  failedStep?: string;
  compensationErrors: string[];

  // Timing
  startedAt: string;
  completedAt?: string;
}
```


<details>
<summary>💡 Hint 1: Direction</summary>
Define a `SagaStep` interface with `execute()` and `compensate()` methods. The orchestrator iterates steps, tracking completed ones so it knows what to undo on failure.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Each step's `execute()` calls a service API and stores the result in the saga context (e.g., `ctx.paymentId`). Each `compensate()` checks if there is anything to undo (`if (!ctx.paymentId) return`) and calls the reversal API.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
Use the saga ID as the payment's `orderId` for idempotency. The notification step's `compensate()` is a no-op. On failure, reverse through `[...completedSteps].reverse()` calling each step's `compensate()`. Set status to COMPENSATING then FAILED.
</details>

### 🛠️ Build: The Orchestrator

<details>
<summary>💡 Hint 1: Direction</summary>
Consider the trade-offs between different approaches before choosing one.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Refer back to the patterns introduced earlier in this module.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The solution uses the same technique shown in the examples above, adapted to this specific scenario.
</details>


```typescript
// src/sagas/purchaseSaga.ts

import { v4 as uuidv4 } from 'uuid';
import { SagaContext, SagaStep, SagaStatus } from './types';

// In-memory saga store (in production: persist to a database)
const sagas: Map<string, SagaContext> = new Map();

// Step 1: Reserve the ticket
const reserveTicketStep: SagaStep = {
  name: 'RESERVING_TICKET',

  async execute(ctx: SagaContext): Promise<void> {
    console.log(`[saga:${ctx.sagaId}] Step 1: Reserving ticket for event ${ctx.eventId}`);

    // Call the event/ticket service
    const response = await fetch(`${process.env.EVENT_SERVICE_URL || 'http://localhost:3000'}/api/events/${ctx.eventId}/reserve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId: ctx.userId, tier: ctx.tier }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Reservation failed: ${error.message}`);
    }

    const result = await response.json();
    ctx.reservationId = result.data.reservationId;
    ctx.ticketId = result.data.ticketId;
    ctx.amountInCents = result.data.priceInCents;

    console.log(`[saga:${ctx.sagaId}] Ticket reserved: ${ctx.ticketId}`);
  },

  async compensate(ctx: SagaContext): Promise<void> {
    if (!ctx.reservationId) return; // Nothing to compensate

    console.log(`[saga:${ctx.sagaId}] COMPENSATING: Releasing reservation ${ctx.reservationId}`);

    try {
      await fetch(`${process.env.EVENT_SERVICE_URL || 'http://localhost:3000'}/api/reservations/${ctx.reservationId}/release`, {
        method: 'POST',
      });
      console.log(`[saga:${ctx.sagaId}] Reservation ${ctx.reservationId} released`);
    } catch (err) {
      const msg = `Failed to release reservation: ${(err as Error).message}`;
      console.error(`[saga:${ctx.sagaId}] ${msg}`);
      ctx.compensationErrors.push(msg);
    }
  },
};

// Step 2: Process the payment
const processPaymentStep: SagaStep = {
  name: 'PROCESSING_PAYMENT',

  async execute(ctx: SagaContext): Promise<void> {
    console.log(`[saga:${ctx.sagaId}] Step 2: Processing payment $${((ctx.amountInCents || 0) / 100).toFixed(2)}`);

    const response = await fetch(`${process.env.PAYMENT_SERVICE_URL || 'http://localhost:3001'}/api/payments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        orderId: ctx.sagaId, // Use saga ID as idempotency key
        amountInCents: ctx.amountInCents,
        currency: 'USD',
        paymentMethod: ctx.paymentMethod,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Payment failed: ${error.message}`);
    }

    const result = await response.json();
    ctx.paymentId = result.data.id;

    console.log(`[saga:${ctx.sagaId}] Payment processed: ${ctx.paymentId}`);
  },

  async compensate(ctx: SagaContext): Promise<void> {
    if (!ctx.paymentId) return;

    console.log(`[saga:${ctx.sagaId}] COMPENSATING: Refunding payment ${ctx.paymentId}`);

    try {
      await fetch(`${process.env.PAYMENT_SERVICE_URL || 'http://localhost:3001'}/api/payments/${ctx.paymentId}/refund`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: `Saga ${ctx.sagaId} compensation` }),
      });
      console.log(`[saga:${ctx.sagaId}] Payment ${ctx.paymentId} refunded`);
    } catch (err) {
      const msg = `Failed to refund payment: ${(err as Error).message}`;
      console.error(`[saga:${ctx.sagaId}] ${msg}`);
      ctx.compensationErrors.push(msg);
    }
  },
};

// Step 3: Confirm the order
const confirmOrderStep: SagaStep = {
  name: 'CONFIRMING_ORDER',

  async execute(ctx: SagaContext): Promise<void> {
    console.log(`[saga:${ctx.sagaId}] Step 3: Confirming order`);

    const response = await fetch(`${process.env.ORDER_SERVICE_URL || 'http://localhost:3000'}/api/orders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        userId: ctx.userId,
        ticketId: ctx.ticketId,
        paymentId: ctx.paymentId,
        eventId: ctx.eventId,
        amountInCents: ctx.amountInCents,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Order confirmation failed: ${error.message}`);
    }

    const result = await response.json();
    ctx.orderId = result.data.id;

    console.log(`[saga:${ctx.sagaId}] Order confirmed: ${ctx.orderId}`);
  },

  async compensate(ctx: SagaContext): Promise<void> {
    if (!ctx.orderId) return;

    console.log(`[saga:${ctx.sagaId}] COMPENSATING: Cancelling order ${ctx.orderId}`);

    try {
      await fetch(`${process.env.ORDER_SERVICE_URL || 'http://localhost:3000'}/api/orders/${ctx.orderId}/cancel`, {
        method: 'POST',
      });
      console.log(`[saga:${ctx.sagaId}] Order ${ctx.orderId} cancelled`);
    } catch (err) {
      const msg = `Failed to cancel order: ${(err as Error).message}`;
      console.error(`[saga:${ctx.sagaId}] ${msg}`);
      ctx.compensationErrors.push(msg);
    }
  },
};

// Step 4: Send notification (best-effort, no compensation)
const sendNotificationStep: SagaStep = {
  name: 'SENDING_NOTIFICATION',

  async execute(ctx: SagaContext): Promise<void> {
    console.log(`[saga:${ctx.sagaId}] Step 4: Sending notification`);

    // Publish to Kafka — fire and forget
    // If this fails, we log it but don't compensate the entire purchase
    try {
      const { publishEvent } = await import('../messaging/kafkaProducer');
      await publishEvent('ticket-purchases', ctx.eventId, {
        type: 'TicketPurchased',
        sagaId: ctx.sagaId,
        occurredAt: new Date().toISOString(),
        payload: {
          orderId: ctx.orderId,
          ticketId: ctx.ticketId,
          eventId: ctx.eventId,
          customerEmail: ctx.email,
          amountInCents: ctx.amountInCents,
        },
      });

      console.log(`[saga:${ctx.sagaId}] Notification event published`);
    } catch (err) {
      console.warn(`[saga:${ctx.sagaId}] Notification failed (non-critical): ${(err as Error).message}`);
      // Do NOT throw — notification failure should not fail the saga
    }
  },

  async compensate(_ctx: SagaContext): Promise<void> {
    // No compensation for notifications — they are best-effort
  },
};

// The ordered list of saga steps
const STEPS: SagaStep[] = [
  reserveTicketStep,
  processPaymentStep,
  confirmOrderStep,
  sendNotificationStep,
];

// The saga executor
export async function executePurchaseSaga(input: {
  eventId: string;
  userId: string;
  email: string;
  paymentMethod: string;
  tier: string;
}): Promise<SagaContext> {
  const ctx: SagaContext = {
    sagaId: `saga_${uuidv4()}`,
    status: 'STARTED',
    ...input,
    compensationErrors: [],
    startedAt: new Date().toISOString(),
  };

  sagas.set(ctx.sagaId, ctx);
  console.log(`[saga:${ctx.sagaId}] Purchase saga started`);

  let completedSteps: SagaStep[] = [];

  for (const step of STEPS) {
    ctx.status = step.name as SagaStatus;

    try {
      await step.execute(ctx);
      completedSteps.push(step);
    } catch (err) {
      ctx.error = (err as Error).message;
      ctx.failedStep = step.name;
      console.error(`[saga:${ctx.sagaId}] Step "${step.name}" failed: ${ctx.error}`);

      // Compensate in reverse order
      ctx.status = 'COMPENSATING';
      console.log(`[saga:${ctx.sagaId}] Starting compensation (${completedSteps.length} steps to undo)`);

      // Spread to avoid mutating the original array
      for (const completedStep of [...completedSteps].reverse()) {
        await completedStep.compensate(ctx);
      }

      ctx.status = 'FAILED';
      ctx.completedAt = new Date().toISOString();

      console.log(`[saga:${ctx.sagaId}] Saga FAILED. Compensation complete.`);
      if (ctx.compensationErrors.length > 0) {
        console.error(`[saga:${ctx.sagaId}] Compensation errors:`, ctx.compensationErrors);
      }

      return ctx;
    }
  }

  ctx.status = 'COMPLETED';
  ctx.completedAt = new Date().toISOString();
  console.log(`[saga:${ctx.sagaId}] Saga COMPLETED successfully`);

  return ctx;
}

// Get saga status (for API)
export function getSagaStatus(sagaId: string): SagaContext | undefined {
  return sagas.get(sagaId);
}
```

### Wire the Saga Into the Purchase Endpoint

```typescript
// src/routes/tickets.ts — updated to use the saga

import { executePurchaseSaga, getSagaStatus } from '../sagas/purchaseSaga';

app.post('/api/events/:eventId/tickets', async (req, res) => {
  const result = await executePurchaseSaga({
    eventId: req.params.eventId,
    userId: req.user.id, // From JWT middleware
    email: req.body.email,
    paymentMethod: req.body.paymentMethod,
    tier: req.body.tier || 'general',
  });

  if (result.status === 'FAILED') {
    return res.status(422).json({
      error: 'PURCHASE_FAILED',
      message: result.error,
      sagaId: result.sagaId,
      failedStep: result.failedStep,
      compensationErrors: result.compensationErrors,
    });
  }

  return res.status(201).json({
    data: {
      orderId: result.orderId,
      ticketId: result.ticketId,
      paymentId: result.paymentId,
      sagaId: result.sagaId,
    },
  });
});

// Status endpoint for long-running sagas
app.get('/api/sagas/:sagaId', (req, res) => {
  const saga = getSagaStatus(req.params.sagaId);
  if (!saga) {
    return res.status(404).json({ error: 'NOT_FOUND' });
  }
  res.json({ data: saga });
});
```

---

## 3. Debug: Inject Failures (15 minutes)

### 🐛 Test Failure at Step 3 (Order Confirmation)

<details>
<summary>💡 Hint 1: Direction</summary>
Consider the trade-offs between different approaches before choosing one.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Refer back to the patterns introduced earlier in this module.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The solution uses the same technique shown in the examples above, adapted to this specific scenario.
</details>


Add a way to inject failures for testing:

```typescript
// Environment variable to control failure injection
const FAIL_AT_STEP = process.env.FAIL_AT_STEP; // e.g., "CONFIRMING_ORDER"

// In the saga executor, before each step:
if (FAIL_AT_STEP === step.name) {
  throw new Error(`[INJECTED FAILURE] Step ${step.name} failed by configuration`);
}
```

Now test:

```bash
# Set the failure injection
docker compose exec monolith sh -c 'export FAIL_AT_STEP=CONFIRMING_ORDER'

# Or pass it as an environment variable in docker-compose.yml:
# environment:
#   FAIL_AT_STEP: CONFIRMING_ORDER
```

```bash
# Purchase a ticket
curl -s -X POST http://localhost:8080/api/events/1/tickets \
  -H 'Content-Type: application/json' \
  -d '{"email": "saga-test@example.com", "paymentMethod": "tok_visa"}' | jq .
```

Expected response:

```json
{
  "error": "PURCHASE_FAILED",
  "message": "[INJECTED FAILURE] Step CONFIRMING_ORDER failed by configuration",
  "sagaId": "saga_abc123",
  "failedStep": "CONFIRMING_ORDER",
  "compensationErrors": []
}
```

Watch the logs:

```
[saga:saga_abc123] Purchase saga started
[saga:saga_abc123] Step 1: Reserving ticket for event 1
[saga:saga_abc123] Ticket reserved: tkt_xyz
[saga:saga_abc123] Step 2: Processing payment $150.00
[saga:saga_abc123] Payment processed: pay_def
[saga:saga_abc123] Step "CONFIRMING_ORDER" failed: [INJECTED FAILURE]
[saga:saga_abc123] Starting compensation (2 steps to undo)
[saga:saga_abc123] COMPENSATING: Refunding payment pay_def
[saga:saga_abc123] Payment pay_def refunded
[saga:saga_abc123] COMPENSATING: Releasing reservation res_ghi
[saga:saga_abc123] Reservation res_ghi released
[saga:saga_abc123] Saga FAILED. Compensation complete.
```


<details>
<summary>💡 Hint 1: Direction</summary>
Use an environment variable like `FAIL_AT_STEP` to inject failures at specific saga steps without modifying service code.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Before each step executes, check `if (FAIL_AT_STEP === step.name) throw new Error(...)`. Test with each step name and verify the correct number of compensations fire.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
When CONFIRMING_ORDER fails, you should see two compensations in the logs: refund payment then release reservation. Verify by checking the payment status is "refunded" and the reservation seat is available again.
</details>

### 🔍 Verify Consistency

After the saga fails and compensates, check:

```bash
# The payment should be refunded
curl -s http://localhost:3001/api/payments/pay_def | jq .status
# Expected: "refunded"

# The reservation should be released
# (check your event service — the seat should be available again)
```

The system is consistent. The customer was not charged. The seat is available. No partial state remains.

### 🐛 Test Failure at Each Step

<details>
<summary>💡 Hint 1: Direction</summary>
Consider the trade-offs between different approaches before choosing one.
</details>

<details>
<summary>💡 Hint 2: Approach</summary>
Refer back to the patterns introduced earlier in this module.
</details>

<details>
<summary>💡 Hint 3: Almost There</summary>
The solution uses the same technique shown in the examples above, adapted to this specific scenario.
</details>


Repeat the test with `FAIL_AT_STEP` set to each step name:

| FAIL_AT_STEP | Steps to Compensate | Expected Compensation |
|---|---|---|
| `RESERVING_TICKET` | 0 | Nothing to undo |
| `PROCESSING_PAYMENT` | 1 | Release reservation |
| `CONFIRMING_ORDER` | 2 | Refund payment, release reservation |
| `SENDING_NOTIFICATION` | 0 | None (notification failure does not trigger compensation) |

---

## 4. Choreography vs Orchestration (10 minutes)

We built an **orchestrated** saga — a central orchestrator coordinates the steps and handles compensation. The alternative is **choreography** — each service listens for events and decides what to do next.

### Choreographed Version

```
Event Service                 Payment Service             Order Service
     │                              │                          │
     │ TicketReserved              │                          │
     │─────────────────────────────→│                          │
     │                              │ PaymentProcessed         │
     │                              │─────────────────────────→│
     │                              │                          │ OrderConfirmed
     │                              │                          │──→ Notification
     │                              │                          │
     │         PaymentFailed        │                          │
     │←─────────────────────────────│                          │
     │ ReleaseReservation           │                          │
```

Each service reacts to events. No central coordinator. Sounds elegant. But:

1. **Where is the complete flow?** It is distributed across every service. Nobody can see the big picture.
2. **How do you add a step?** You modify multiple services. A change to the flow requires coordinating deployments.
3. **How do you debug a failure?** You search logs across every service, correlating events by an ID you hope was propagated correctly.
4. **Cyclic dependencies:** Service A listens to Service B which listens to Service A. Event spaghetti.

### Orchestrated Version (What We Built)

```
                 Saga Orchestrator
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
  Event Service   Payment Service   Order Service
```

The orchestrator knows the complete flow. Adding a step means changing one file. Debugging means reading the saga log. Compensation logic is in one place.

### When to Use Each

| | Choreography | Orchestration |
|---|---|---|
| Simple flows (2-3 steps) | Good fit | Overkill |
| Complex flows (4+ steps with compensation) | Event spaghetti | Good fit |
| Visibility | Poor (distributed) | Good (centralized) |
| Coupling | Services are loosely coupled | Services coupled to orchestrator |
| Single point of failure | None | The orchestrator |

**For TicketPulse's purchase flow:** Orchestration is the right choice. Four steps, money involved, multiple compensation paths. You need visibility and control.

**For simple reactions:** Choreography is fine. "When a ticket is purchased, update the analytics dashboard" does not need an orchestrator.

---

## 5. The Hard Parts (10 minutes)

### ⚠️ Common Mistake: Non-Idempotent Compensating Actions

What if the refund compensation is called twice (e.g., due to a network retry)?

```
Compensation attempt 1: Refund $150 ← OK
Compensation attempt 2: Refund $150 ← DOUBLE REFUND!
```

Every compensating action MUST be idempotent. The refund endpoint should check: "Has this payment already been refunded?" If yes, return success without refunding again. We already built this in M31:

```typescript
if (payment.status === 'refunded') {
  return res.status(200).json({ data: payment }); // Idempotent — already refunded
}
```

### What If Compensation Fails?

If the refund API is down when you try to compensate, you have a partially compensated saga. This is the hardest problem in distributed systems.

Options:
1. **Retry with backoff:** Try the compensation again after a delay. Most compensation failures are transient (network issues, service restarts).
2. **Dead letter the saga:** Record the saga state in a dead letter table. A background process retries failed compensations periodically.
3. **Manual intervention:** Alert an operator. Some failures (double charge, lost reservation) require human judgment.

In production, all three are combined. Retry first, dead letter if retries exhaust, alert if the dead letter ages beyond a threshold.

> **The bigger picture:** Real-World Sagas

Uber's trip lifecycle is a saga:

```
1. Match rider with driver     → Compensate: cancel match
2. Driver accepts              → Compensate: release driver
3. Driver picks up rider       → Compensate: (cannot undo physical action)
4. Trip in progress            → Compensate: end trip early, adjust fare
5. Drop off rider              → Compensate: (cannot undo)
6. Charge payment              → Compensate: refund
7. Driver and rider rate each other → Compensate: (best-effort, no undo)
```

Notice: some steps cannot be compensated (physical actions like pickup). This is why saga design is hard — you must identify which steps are reversible and which are not, and plan accordingly.

---

## 6. Reflect (5 minutes)

### 🤔 Questions

1. **Why not use a distributed transaction (two-phase commit) instead of a saga?** What would that require from every service?

2. **The notification step does not trigger compensation on failure. Is that the right decision?** What if the notification was a regulatory requirement (e.g., "customer must receive a receipt within 60 seconds")?

3. **How would you test a saga in CI?** You need all services running. Is that practical? What alternatives exist?

4. **If you had to add a fifth step (fraud check before payment), where would you insert it? What compensating action would it have?**

---

> **What did you notice?** The saga code is significantly more complex than the original single-transaction version. Is this accidental complexity or essential complexity? When does a saga become worth the investment?

## 7. Checkpoint

After this module, TicketPulse should have:

- [ ] A saga orchestrator in `src/sagas/purchaseSaga.ts` that coordinates the purchase flow
- [ ] Four saga steps: reserve ticket, process payment, confirm order, send notification
- [ ] Compensating actions for each reversible step (release reservation, refund payment, cancel order)
- [ ] A saga status API (`GET /api/sagas/:sagaId`) for tracking saga progress
- [ ] Demonstrated: inject failure at step 3, verify compensation (refund + release)
- [ ] All compensating actions are idempotent
- [ ] Understanding of choreography vs orchestration trade-offs
- [ ] Understanding of why compensation failures are the hardest problem

---

## Module Summary

| Concept | Key Takeaway |
|---------|-------------|
| **Saga pattern** | A sequence of local transactions with compensating actions. Used instead of distributed transactions across services. |
| **Compensating action** | An operation that undoes the effect of a previous step. Must be idempotent. |
| **Orchestration** | A central coordinator drives the saga. Knows the complete flow. Good for complex multi-step processes. |
| **Choreography** | Services react to events with no central coordinator. Good for simple flows. Becomes event spaghetti for complex ones. |
| **Idempotent compensation** | Compensating actions must produce the same result regardless of how many times they are called. Critical for reliability. |
| **Partial compensation** | When a compensating action fails, the saga is in an inconsistent state. Handle with retries, dead letters, and manual intervention. |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Saga** | A pattern for managing data consistency across microservices using a sequence of local transactions and compensating actions. |
| **Compensating action** | An operation that semantically undoes a completed transaction. Not a rollback — it is a new action that reverses the effect. |
| **Orchestration** | A saga execution style where a central orchestrator tells each service what to do and handles failures. |
| **Choreography** | A saga execution style where each service listens for events and decides independently what to do next. |
| **Two-phase commit (2PC)** | A distributed transaction protocol where all participants agree to commit or abort. Requires locking and a coordinator. Rarely used in microservices due to performance and availability concerns. |
| **Idempotent** | An operation that produces the same result regardless of how many times it is executed. |
| **Dead letter** | A message or saga state that failed processing and is set aside for later inspection or retry. |

---

---

## What's Next

In **Database Per Service** (L2-M35), you'll give each TicketPulse service its own database and confront the real cost of data independence.

---

## Further Reading

- Chris Richardson, *Microservices Patterns*, Chapter 4 (Managing Transactions with Sagas)
- [Temporal](https://temporal.io/) — A workflow engine that handles saga orchestration, retries, and compensation automatically
- Chapter 3 of the 100x Engineer Guide: Section 5 (Event-Driven Patterns — Saga Pattern)
- Caitie McCaffrey, ["Applying the Saga Pattern"](https://www.youtube.com/watch?v=xDuwrtwYHu8) — conference talk on real-world saga implementations
