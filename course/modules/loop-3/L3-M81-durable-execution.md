# L3-M81: Durable Execution

> **Loop 3 (Mastery)** | Section 3D: The Cutting Edge | ⏱️ 75 min | 🟡 Deep Dive | Prerequisites: L2-M34
>
> **Source:** Chapter 10 of the 100x Engineer Guide

## What You'll Learn

- Why long-running, multi-step processes are fragile when the orchestrator can crash at any point
- How durable execution makes code survive crashes, restarts, and deploys by persisting function state
- Building TicketPulse's purchase saga as a durable workflow where each step is automatically persisted
- Deterministic replay: the runtime replays the workflow log to reconstruct state after a crash
- Human-in-the-loop patterns: pausing a workflow to wait for admin approval before resuming
- Which TicketPulse flows benefit most from durable execution

## Why This Matters

In L2-M34, you built the purchase saga: reserve tickets, charge payment, confirm order, send email. It works. But there is a question we sidestepped: what happens if the orchestrator crashes between step 2 (payment charged) and step 3 (order confirmed)?

The payment went through. The customer was charged. But the order was never confirmed and the tickets were never assigned. You have taken their money and given them nothing. The saga compensations cannot help because the orchestrator itself is gone -- its in-memory state is lost.

This is not a theoretical concern. Processes crash. Kubernetes pods get evicted. Deployments roll. Memory runs out. Any multi-step process that holds state only in memory is one OOM-kill away from an inconsistent state that requires manual intervention to fix.

Durable execution solves this. The core idea: persist the execution state of your workflow at every step. If the process dies after step 2, a new process picks up the workflow and resumes at step 3. The code looks like normal sequential code -- no state machines, no explicit checkpointing, no manual recovery logic. The runtime handles it.

Temporal (the leading durable execution platform) processes over 1 billion workflow executions per month at companies like Netflix, Snap, Stripe, and Coinbase. This is not experimental technology. It is how the most reliability-conscious organizations in the world run their critical business processes.

---

### 🤔 Prediction Prompt

Before reading the solution, think about the purchase saga from L2-M34. If the orchestrator crashes between "payment charged" and "order confirmed," what recovery mechanism do you currently have? What state is lost?

## 1. The Problem: Fragile Multi-Step Processes

### What Can Go Wrong

Consider the purchase saga from L2-M34:

```
Step 1: Reserve tickets      ✅ Completed
Step 2: Charge payment        ✅ Completed
--- PROCESS CRASHES HERE ---
Step 3: Confirm order         ❌ Never executed
Step 4: Send confirmation     ❌ Never executed
```

The customer sees a charge on their credit card but no tickets. Your support team gets a ticket. Someone has to manually investigate, check the payment provider, update the database, and send the email. At scale, this happens daily.

### Why Retries and Queues Are Not Enough

You might think: "I will put each step on a message queue. If one fails, the queue retries it." That helps with transient failures within a step, but it does not solve the orchestration problem:

- Who tracks which steps have completed?
- What if the retry logic itself crashes?
- How do you handle steps that depend on results from previous steps?
- How do you implement timeouts that span hours or days (wait for admin approval)?

Message queues are great for individual task execution. But orchestrating a sequence of dependent steps with branching logic, timeouts, and human approval requires something more.

---

## 2. Durable Execution: Code That Survives Crashes

### The Core Idea

Durable execution platforms (Temporal, Restate, Inngest) persist the execution state of your workflow transparently. Your code looks like a normal function with sequential steps:

```typescript
// This looks like normal code. But every step is persisted.
async function purchaseWorkflow(ctx: WorkflowContext, order: OrderRequest) {
  // Step 1: Reserve tickets
  const reservation = await ctx.run('reserve-tickets', () =>
    ticketService.reserve(order.eventId, order.seats)
  );

  // Step 2: Charge payment
  const payment = await ctx.run('charge-payment', () =>
    paymentService.charge(order.userId, reservation.totalAmount)
  );

  // Step 3: Confirm order
  const confirmation = await ctx.run('confirm-order', () =>
    orderService.confirm(reservation.id, payment.id)
  );

  // Step 4: Send confirmation email
  await ctx.run('send-email', () =>
    emailService.sendConfirmation(order.userId, confirmation)
  );

  return confirmation;
}
```

The magic is in `ctx.run()`. Every time a step completes, the result is persisted to durable storage (typically a database). If the process crashes after step 2:

1. A new worker picks up the workflow
2. The runtime sees steps 1 and 2 already have stored results
3. It skips those steps (returns the stored results without re-executing)
4. Execution resumes at step 3

The developer writes sequential code. The runtime handles crash recovery.

### How It Works: The Event History

Under the hood, the runtime maintains an event history for each workflow execution:

```
Event Log for workflow execution wf_abc123:
┌─────┬──────────────────────┬───────────────────────────────────┐
│  #  │ Event Type           │ Data                              │
├─────┼──────────────────────┼───────────────────────────────────┤
│  1  │ WorkflowStarted      │ {orderId: "ord_789", seats: [...]}│
│  2  │ StepScheduled        │ {name: "reserve-tickets"}         │
│  3  │ StepCompleted        │ {result: {reservationId: "res_1"}}│
│  4  │ StepScheduled        │ {name: "charge-payment"}          │
│  5  │ StepCompleted        │ {result: {paymentId: "pay_456"}}  │
│  6  │ StepScheduled        │ {name: "confirm-order"}           │
│     │ --- CRASH HERE ---   │                                   │
│     │ --- NEW WORKER ---   │                                   │
│  7  │ StepCompleted        │ {result: {orderId: "ord_789"}}    │
│  8  │ StepScheduled        │ {name: "send-email"}              │
│  9  │ StepCompleted        │ {result: {sent: true}}            │
│ 10  │ WorkflowCompleted    │ {orderId: "ord_789"}              │
└─────┴──────────────────────┴───────────────────────────────────┘
```

When a new worker picks up the workflow, it replays the event history. Steps 1-2 already have results, so the runtime returns the stored results without calling the actual functions. Step 3 does not have a result, so the runtime executes it for real.

---

## 3. Deterministic Replay: The Critical Constraint

### Why Workflow Code Must Be Deterministic

The replay mechanism means the workflow code runs again on a new worker. The runtime needs the code to take the same path it took originally -- otherwise it cannot match events from the history to steps in the code.

This means workflow code must be **deterministic**: given the same inputs and stored results, it must make the same decisions every time.

### What You Cannot Do in Workflow Code

```typescript
// BAD: Non-deterministic workflow code

async function badWorkflow(ctx: WorkflowContext) {
  // ❌ Math.random() returns different values on replay
  if (Math.random() > 0.5) {
    await ctx.run('path-a', () => doA());
  } else {
    await ctx.run('path-b', () => doB());
  }

  // ❌ Date.now() returns different values on replay
  const deadline = Date.now() + 3600000;

  // ❌ Reading environment variables that might change between deploys
  const config = process.env.FEATURE_FLAG;

  // ❌ Direct API calls (not wrapped in ctx.run)
  const data = await fetch('https://api.example.com/data');
}
```

### What You Can Do

```typescript
// GOOD: Deterministic workflow code

async function goodWorkflow(ctx: WorkflowContext) {
  // ✅ Use the workflow context for random values
  const coinFlip = await ctx.run('random-decision', () =>
    Math.random() > 0.5 ? 'a' : 'b'
  );

  if (coinFlip === 'a') {
    await ctx.run('path-a', () => doA());
  } else {
    await ctx.run('path-b', () => doB());
  }

  // ✅ Use the workflow context for time
  const now = ctx.currentTime();

  // ✅ All side effects go through ctx.run() (activities)
  const data = await ctx.run('fetch-data', () =>
    fetch('https://api.example.com/data').then(r => r.json())
  );
}
```

The rule is simple: **side effects (I/O, randomness, time) go into activities (ctx.run). Workflow code is pure logic that branches on activity results.**

### Stop and Think (5 minutes)

Look at the purchase workflow above. Could you add a step that generates a random discount code for the confirmation email? Where would the randomness live -- in workflow code or in an activity? Why?

---

## 4. Build: TicketPulse Durable Purchase Workflow

### The Full Implementation

Here is the complete purchase workflow with error handling, compensation, and timeouts:

```typescript
// workflows/purchase.ts
import { WorkflowContext, WorkflowTimeoutError } from './workflow-engine';
import { ticketService, paymentService, orderService, emailService } from '../services';

interface PurchaseRequest {
  userId: string;
  eventId: string;
  seats: string[];
  paymentMethodId: string;
}

export async function purchaseWorkflow(
  ctx: WorkflowContext,
  request: PurchaseRequest
): Promise<{ orderId: string; status: string }> {

  // Step 1: Reserve tickets (with timeout)
  const reservation = await ctx.run('reserve-tickets', () =>
    ticketService.reserve(request.eventId, request.seats)
  );

  try {
    // Step 2: Charge payment
    const payment = await ctx.run('charge-payment', () =>
      paymentService.charge({
        userId: request.userId,
        amount: reservation.totalAmount,
        currency: reservation.currency,
        paymentMethodId: request.paymentMethodId,
        idempotencyKey: `purchase-${ctx.workflowId}`,
      })
    );

    // Step 3: Confirm order
    const order = await ctx.run('confirm-order', () =>
      orderService.confirm({
        reservationId: reservation.id,
        paymentId: payment.id,
        userId: request.userId,
      })
    );

    // Step 4: Send confirmation (non-critical -- don't fail the workflow)
    await ctx.run('send-confirmation', () =>
      emailService.sendPurchaseConfirmation({
        userId: request.userId,
        orderId: order.id,
        seats: request.seats,
        eventId: request.eventId,
      })
    ).catch(err => {
      console.error('Email failed, will retry separately:', err);
    });

    return { orderId: order.id, status: 'confirmed' };

  } catch (error) {
    // Compensation: release the reservation if payment or confirmation fails
    await ctx.run('compensate-release-tickets', () =>
      ticketService.release(reservation.id)
    );

    throw error;
  }
}
```

### The Workflow Engine (Simplified)

A production system would use Temporal, Restate, or Inngest. Here is a simplified engine that demonstrates the core concepts:

```typescript
// workflow-engine.ts
import { db } from '../database';

interface WorkflowEvent {
  id: number;
  workflowId: string;
  stepName: string;
  type: 'scheduled' | 'completed' | 'failed';
  data: any;
  createdAt: Date;
}

export class WorkflowContext {
  workflowId: string;
  private history: WorkflowEvent[] = [];
  private replayIndex: number = 0;

  constructor(workflowId: string, history: WorkflowEvent[]) {
    this.workflowId = workflowId;
    this.history = history;
  }

  currentTime(): Date {
    // Return the time from the original execution during replay
    const event = this.history[this.replayIndex];
    if (event) return event.createdAt;
    return new Date();
  }

  async run<T>(stepName: string, fn: () => Promise<T>): Promise<T> {
    // Check if this step already has a result in the history
    const existingResult = this.history.find(
      e => e.stepName === stepName && e.type === 'completed'
    );

    if (existingResult) {
      console.log(`[replay] Skipping "${stepName}" — using stored result`);
      this.replayIndex++;
      return existingResult.data as T;
    }

    const existingFailure = this.history.find(
      e => e.stepName === stepName && e.type === 'failed'
    );

    if (existingFailure) {
      console.log(`[replay] Skipping "${stepName}" — replaying failure`);
      this.replayIndex++;
      throw new Error(existingFailure.data.message);
    }

    // No existing result — execute the step for real
    console.log(`[execute] Running "${stepName}"...`);

    // Record that we scheduled this step
    await db.query(
      `INSERT INTO workflow_events (workflow_id, step_name, type, data)
       VALUES ($1, $2, 'scheduled', $3)`,
      [this.workflowId, stepName, {}]
    );

    try {
      const result = await fn();

      // Persist the result
      await db.query(
        `INSERT INTO workflow_events (workflow_id, step_name, type, data)
         VALUES ($1, $2, 'completed', $3)`,
        [this.workflowId, stepName, JSON.stringify(result)]
      );

      return result;

    } catch (error) {
      // Persist the failure
      await db.query(
        `INSERT INTO workflow_events (workflow_id, step_name, type, data)
         VALUES ($1, $2, 'failed', $3)`,
        [this.workflowId, stepName, JSON.stringify({ message: (error as Error).message })]
      );

      throw error;
    }
  }
}
```

### The Workflow Runner

```typescript
// workflow-runner.ts
import { db } from '../database';
import { WorkflowContext } from './workflow-engine';
import { purchaseWorkflow } from './purchase';

export async function startWorkflow(
  workflowId: string,
  request: any
): Promise<void> {
  // Record the workflow
  await db.query(
    `INSERT INTO workflows (id, type, input, status)
     VALUES ($1, 'purchase', $2, 'running')
     ON CONFLICT (id) DO NOTHING`,
    [workflowId, JSON.stringify(request)]
  );

  await executeWorkflow(workflowId, request);
}

async function executeWorkflow(
  workflowId: string,
  request: any
): Promise<void> {
  // Load event history
  const { rows: history } = await db.query(
    `SELECT * FROM workflow_events
     WHERE workflow_id = $1
     ORDER BY id ASC`,
    [workflowId]
  );

  const ctx = new WorkflowContext(workflowId, history);

  try {
    const result = await purchaseWorkflow(ctx, request);

    await db.query(
      `UPDATE workflows SET status = 'completed', output = $2 WHERE id = $1`,
      [workflowId, JSON.stringify(result)]
    );
  } catch (error) {
    await db.query(
      `UPDATE workflows SET status = 'failed', output = $2 WHERE id = $1`,
      [workflowId, JSON.stringify({ error: (error as Error).message })]
    );
  }
}

// Recovery: find workflows that were running when the process died
export async function recoverStuckWorkflows(): Promise<void> {
  const { rows } = await db.query(
    `SELECT id, input FROM workflows
     WHERE status = 'running'
     AND updated_at < NOW() - INTERVAL '30 seconds'`
  );

  for (const workflow of rows) {
    console.log(`[recovery] Resuming workflow ${workflow.id}`);
    await executeWorkflow(workflow.id, JSON.parse(workflow.input));
  }
}
```

---

## 5. Try It: Crash Recovery in Action

### The Experiment

Start a purchase workflow, kill the process mid-execution, restart, and watch it resume.

```bash
# Terminal 1: Start the workflow runner
node workflow-runner.js

# Terminal 2: Trigger a purchase
curl -X POST http://localhost:3000/api/purchase \
  -H 'Content-Type: application/json' \
  -d '{"userId": "u_1", "eventId": "evt_1", "seats": ["A-1", "A-2"]}'

# Watch the output in Terminal 1:
# [execute] Running "reserve-tickets"...
# [execute] Running "charge-payment"...
```

Now simulate a crash:

```bash
# Terminal 1: Kill the process after "charge-payment" completes
# (Ctrl+C or kill the process)

# Check the database — the workflow is stuck in "running" status
psql -c "SELECT id, status FROM workflows WHERE status = 'running';"
#  id       | status
# ----------+--------
#  wf_abc123 | running

# Check event history — two steps completed
psql -c "SELECT step_name, type FROM workflow_events WHERE workflow_id = 'wf_abc123';"
#  step_name       | type
# -----------------+-----------
#  reserve-tickets  | scheduled
#  reserve-tickets  | completed
#  charge-payment   | scheduled
#  charge-payment   | completed
```

Restart the process:

```bash
# Terminal 1: Restart
node workflow-runner.js

# The recovery process finds the stuck workflow:
# [recovery] Resuming workflow wf_abc123
# [replay] Skipping "reserve-tickets" — using stored result
# [replay] Skipping "charge-payment" — using stored result
# [execute] Running "confirm-order"...
# [execute] Running "send-confirmation"...
```

Steps 1 and 2 were not re-executed. The payment was not charged again. The workflow resumed exactly where it left off.

---

## 6. Human-in-the-Loop: Pausing for Approval

Some workflows need to wait for human input. A high-value refund might need manager approval. An event creation might need compliance review.

```typescript
// workflows/refund.ts
export async function refundWorkflow(
  ctx: WorkflowContext,
  request: RefundRequest
): Promise<{ refundId: string; status: string }> {

  // Step 1: Validate the refund request
  const validation = await ctx.run('validate-refund', () =>
    refundService.validate(request)
  );

  // Step 2: If amount > $500, wait for manager approval
  if (validation.amount > 50000) { // cents
    console.log('High-value refund — waiting for manager approval');

    // This pauses the workflow. It resumes when an external signal arrives.
    const approval = await ctx.waitForSignal('manager-approval', {
      timeout: '48h', // Auto-reject if no response in 48 hours
    });

    if (!approval.approved) {
      await ctx.run('notify-rejection', () =>
        notificationService.notifyRefundRejected(request.userId, approval.reason)
      );
      return { refundId: '', status: 'rejected' };
    }
  }

  // Step 3: Process the refund
  const refund = await ctx.run('process-refund', () =>
    paymentService.refund(request.paymentId, validation.amount)
  );

  // Step 4: Update order status
  await ctx.run('update-order', () =>
    orderService.updateStatus(request.orderId, 'refunded')
  );

  // Step 5: Notify customer
  await ctx.run('notify-customer', () =>
    emailService.sendRefundConfirmation(request.userId, refund)
  );

  return { refundId: refund.id, status: 'completed' };
}
```

The `waitForSignal` call persists the workflow's state and stops execution. The workflow sits in storage, consuming no compute resources. When the manager clicks "Approve" in the admin panel, an API call sends a signal to the workflow, and it resumes:

```typescript
// API endpoint for manager approval
app.post('/api/admin/refunds/:workflowId/approve', async (req, res) => {
  await workflowEngine.sendSignal(req.params.workflowId, 'manager-approval', {
    approved: true,
    approvedBy: req.user.id,
  });
  res.json({ status: 'signal sent' });
});
```

This workflow can wait for 48 hours without holding a connection, a thread, or any compute resources. When the signal arrives, a worker picks it up and continues.

---

## 7. Design: Where Else Does Durable Execution Help?

### Stop and Design (10 minutes)

<details>
<summary>💡 Hint 1: The decision hinges on what happens when the orchestrator dies mid-step</summary>
For each flow, ask: "If the process crashes between step N and step N+1, is there real business damage (money taken, tickets orphaned)?" If yes, durable execution pays for itself. If the worst case is a retry, simple queues are enough.
</details>

<details>
<summary>💡 Hint 2: Think about Temporal workflow signals for human-in-the-loop steps</summary>
Any flow that pauses for human approval (refund review, event compliance) maps directly to Temporal's `workflow.signal` or Inngest's `waitForEvent` step. If the wait spans hours or days, that is a strong signal for durable execution over in-memory orchestration.
</details>

TicketPulse has several multi-step processes beyond purchasing. For each one, evaluate whether durable execution is worth the complexity:

| Flow | Steps | Duration | Worth It? |
|------|-------|----------|-----------|
| **Refund processing** | Validate, approve, refund, update, notify | Minutes to days | ? |
| **Event creation** | Submit, review, approve, publish, notify organizer | Hours to days | ? |
| **Organizer onboarding** | Sign up, verify identity, review docs, activate | Days to weeks | ? |
| **Ticket transfer** | Request, verify both parties, transfer, notify | Minutes | ? |
| **End-of-event settlement** | Calculate, deduct fees, transfer to organizer, generate report | Hours | ? |

**Guidelines for deciding:**
- If the process has steps that take seconds and never involves human input, a simple try/catch with retries might be enough.
- If the process spans minutes to days, involves human decisions, or has steps where partial failure causes real business damage, durable execution pays for itself.
- If the process has exactly-once requirements (do not charge twice, do not send two refunds), the idempotency guarantees of durable execution are invaluable.

---

## 8. Production Considerations

### Versioning Workflows

When you deploy new code, existing workflows are still running the old version. What happens when the new version changes the step order?

```typescript
// Version 1: reserve → pay → confirm
// Version 2: reserve → validate-fraud → pay → confirm

// A workflow started on v1 has history: [reserve, pay]
// If v2 tries to replay, it expects "validate-fraud" after "reserve"
// but finds "pay" — MISMATCH
```

**Solutions:**
- **Versioned task queues**: Run old and new workers simultaneously. Old workflows finish on old workers.
- **Backward-compatible changes**: Add new optional steps that are skipped during replay if not in history.
- **Workflow migration**: For breaking changes, drain old workflows before deploying new code.

### Observability

Every workflow execution has a complete, queryable history. This is an operational superpower:

```sql
-- Find all workflows that are stuck
SELECT id, type, status, created_at
FROM workflows
WHERE status = 'running'
AND updated_at < NOW() - INTERVAL '1 hour';

-- Find the last completed step for a stuck workflow
SELECT step_name, type, created_at
FROM workflow_events
WHERE workflow_id = 'wf_abc123'
ORDER BY id DESC
LIMIT 1;

-- How long does each step take on average?
SELECT step_name,
       AVG(EXTRACT(EPOCH FROM (completed_at - scheduled_at))) as avg_seconds
FROM workflow_events
WHERE type = 'completed'
GROUP BY step_name;
```

### When NOT to Use Durable Execution

Durable execution adds latency (each step involves a database write) and complexity (determinism constraints, versioning). Do not use it for:

- Simple CRUD operations
- Processes that complete in milliseconds
- Stateless request/response handlers
- Anything that can be made idempotent with a simple retry

---

## Checkpoint: What You Built

You have:

- [x] Understood why in-memory saga orchestration is fragile
- [x] Built a durable purchase workflow that survives process crashes
- [x] Implemented deterministic replay with an event history
- [x] Added human-in-the-loop approval patterns
- [x] Tested crash recovery by killing and restarting the process
- [x] Evaluated which TicketPulse flows benefit from durable execution

**Key insight**: Durable execution makes your code look simple (sequential function calls) while the runtime handles the hard parts (persistence, replay, crash recovery). The constraint is that workflow code must be deterministic -- all side effects go through activities.

---

## Further Exploration

- **Temporal documentation**: The most comprehensive resource on durable execution concepts
- **Restate**: A newer approach that uses a log-based protocol -- lighter weight than Temporal
- **Inngest**: Durable execution as a service -- no infrastructure to manage, ideal for serverless
- Temporal processes 1B+ workflow executions per month at Netflix, Snap, Stripe, and Coinbase
- The concept builds on decades of research in workflow systems, process calculi, and distributed transactions

---

**Next module**: L3-M82 — Event Sourcing at Scale, where we store events instead of state and gain a complete audit trail of every change that ever happened in TicketPulse's order system.

### 🤔 Reflection Prompt

After implementing the purchase saga as a durable workflow, how does the mental model differ from the saga pattern in M34? Where does durable execution eliminate complexity you previously had to manage manually?

## Key Terms

| Term | Definition |
|------|-----------|
| **Durable execution** | A programming model where function state is automatically persisted, surviving crashes and restarts. |
| **Workflow** | A sequence of steps (activities) orchestrated by a durable execution engine to complete a business process. |
| **Deterministic replay** | The technique of re-executing workflow code using recorded results to recover state after a failure. |
| **Temporal** | An open-source durable execution platform that manages workflow state, retries, and timeouts. |
| **Activity** | A single unit of work within a durable workflow that performs a side effect (e.g., API call, database write). |
---

## What's Next

In **Event Sourcing at Scale** (L3-M82), you'll build on what you learned here and take it further.
