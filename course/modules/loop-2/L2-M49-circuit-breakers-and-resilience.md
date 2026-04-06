# L2-M49: Circuit Breakers & Resilience

> **Loop 2 (Practice)** | Section 2D: Advanced Patterns | ⏱️ 60 min | 🟢 Core | Prerequisites: L2-M39 (Kubernetes Basics), L2-M41 (Distributed Tracing)
>
> **Source:** Chapters 3, 22, 25, 32, 13 of the 100x Engineer Guide

---

## The Goal

TicketPulse's order service calls the payment service to charge customers. When the payment service is healthy, everything works. But when it slows down or starts returning errors, the order service keeps sending requests, its threads pile up waiting for responses, and eventually the entire platform goes down. One flaky dependency takes out the whole system.

This is a cascading failure. You will build the defenses against it.

**You will run code within the first two minutes.**

---

## 0. The Problem (3 minutes)

Start by seeing the failure mode. Create a payment service client with no protection:

```typescript
// src/services/payment-client.ts
// NO PROTECTION: This is what we are going to fix.

import axios from 'axios';

const PAYMENT_SERVICE_URL = process.env.PAYMENT_SERVICE_URL || 'http://payment-service:3001';

export interface PaymentResult {
  paymentId: string;
  status: 'success' | 'failed';
}

export async function chargePayment(
  orderId: string,
  amountInCents: number
): Promise<PaymentResult> {
  const response = await axios.post(`${PAYMENT_SERVICE_URL}/charge`, {
    orderId,
    amountInCents,
  });
  return response.data;
}
```

Now simulate the payment service being slow. Create a mock payment server:

```typescript
// test/mock-payment-server.ts

import express from 'express';

const app = express();
app.use(express.json());

let failureMode: 'healthy' | 'slow' | 'error' = 'healthy';

app.post('/charge', async (req, res) => {
  if (failureMode === 'slow') {
    // Simulate a 30-second hang
    await new Promise(resolve => setTimeout(resolve, 30000));
  }
  if (failureMode === 'error') {
    return res.status(500).json({ error: 'Payment service unavailable' });
  }
  res.json({ paymentId: `pay_${Date.now()}`, status: 'success' });
});

// Control endpoint to toggle failure mode
app.post('/admin/failure-mode', (req, res) => {
  failureMode = req.body.mode;
  console.log(`[mock-payment] Failure mode set to: ${failureMode}`);
  res.json({ mode: failureMode });
});

app.listen(3001, () => console.log('[mock-payment] Listening on :3001'));
```

Start the mock server and flip it to error mode:

```bash
npx ts-node test/mock-payment-server.ts &

# In another terminal, trigger errors:
curl -X POST http://localhost:3001/admin/failure-mode -H 'Content-Type: application/json' -d '{"mode":"error"}'

# Try to charge -- every request hits the failing service
for i in $(seq 1 20); do
  curl -s -o /dev/null -w "Request $i: HTTP %{http_code} (%{time_total}s)\n" \
    -X POST http://localhost:3001/charge \
    -H 'Content-Type: application/json' \
    -d '{"orderId":"ord_1","amountInCents":5000}'
done
```

Every request goes to the failing service. Every request waits for a response. Every request gets a 500. The caller wastes time and resources on requests that will never succeed.

---

## 1. Build the Circuit Breaker (15 minutes)

<details>
<summary>💡 Hint 1: Config Values</summary>
Start with these Resilience4j-style defaults: <code>failureThreshold: 5</code> (5 failures to open), <code>failureWindowMs: 10_000</code> (within 10 seconds), <code>openDurationMs: 30_000</code> (stay open 30 seconds before probing), <code>halfOpenMaxProbes: 3</code> (3 successful probes to close). Tune based on your service's p99 latency and traffic volume.
</details>

<details>
<summary>💡 Hint 2: State Transitions</summary>
CLOSED (normal) -> OPEN (after failureThreshold failures in the window) -> HALF_OPEN (after openDurationMs expires) -> back to CLOSED (if halfOpenMaxProbes succeed) or back to OPEN (if any probe fails). Log every transition with <code>[circuit:payment-service] CLOSED -> OPEN</code> for debugging.
</details>

<details>
<summary>💡 Hint 3: Layering Order</summary>
Wrap resilience patterns in this order from outside to inside: Bulkhead (limits concurrency) -> Circuit Breaker (stops calling dead services) -> Retry with exponential backoff and jitter (handles transient failures) -> Timeout (hard limit on any single call). Each layer addresses a different failure mode.
</details>

A circuit breaker has three states:

```
     ┌──────────┐   failure threshold   ┌──────────┐
     │  CLOSED   │ ──────────────────► │   OPEN    │
     │ (normal)  │                      │(fail fast)│
     └──────────┘                      └──────────┘
          ▲                                  │
          │          timeout expires          │
          │                                  ▼
          │                            ┌───────────┐
          └─────── probes succeed ──── │ HALF-OPEN  │
                                       │  (probing) │
                                       └───────────┘
```

- **Closed**: requests pass through normally. Track failures.
- **Open**: requests fail immediately without calling the downstream service.
- **Half-Open**: allow a limited number of probe requests through. If they succeed, close the circuit. If they fail, reopen it.

Implement it:

```typescript
// src/resilience/circuit-breaker.ts

type CircuitState = 'CLOSED' | 'OPEN' | 'HALF_OPEN';

interface CircuitBreakerConfig {
  failureThreshold: number;    // failures before opening
  failureWindowMs: number;     // time window for counting failures
  openDurationMs: number;      // how long to stay open before probing
  halfOpenMaxProbes: number;   // probes allowed in half-open state
}

export class CircuitBreaker {
  private state: CircuitState = 'CLOSED';
  private failures: number[] = [];  // timestamps of recent failures
  private lastOpenedAt: number = 0;
  private halfOpenSuccesses: number = 0;
  private halfOpenFailures: number = 0;

  constructor(
    private name: string,
    private config: CircuitBreakerConfig
  ) {}

  async call<T>(fn: () => Promise<T>): Promise<T> {
    // --- YOUR DECISION POINT ---
    // Before implementing, consider: what should happen when the circuit is open?
    // Option A: throw an error immediately
    // Option B: return a default/cached value
    // Option C: route to a fallback (we will build this in section 3)
    //
    // For now, implement Option A. We will add Option C later.

    if (this.state === 'OPEN') {
      if (this.shouldAttemptProbe()) {
        this.transitionTo('HALF_OPEN');
      } else {
        throw new CircuitOpenError(this.name, this.remainingOpenTime());
      }
    }

    if (this.state === 'HALF_OPEN') {
      return this.executeProbe(fn);
    }

    // CLOSED state: execute normally, track failures
    return this.executeAndTrack(fn);
  }

  private async executeAndTrack<T>(fn: () => Promise<T>): Promise<T> {
    try {
      const result = await fn();
      // Success in closed state -- nothing special to do
      return result;
    } catch (error) {
      this.recordFailure();
      if (this.shouldOpen()) {
        this.transitionTo('OPEN');
      }
      throw error;
    }
  }

  private async executeProbe<T>(fn: () => Promise<T>): Promise<T> {
    try {
      const result = await fn();
      this.halfOpenSuccesses++;
      console.log(`[circuit:${this.name}] Probe succeeded (${this.halfOpenSuccesses}/${this.config.halfOpenMaxProbes})`);

      if (this.halfOpenSuccesses >= this.config.halfOpenMaxProbes) {
        this.transitionTo('CLOSED');
      }
      return result;
    } catch (error) {
      this.halfOpenFailures++;
      console.log(`[circuit:${this.name}] Probe failed, reopening circuit`);
      this.transitionTo('OPEN');
      throw error;
    }
  }

  private recordFailure(): void {
    const now = Date.now();
    this.failures.push(now);
    // Remove failures outside the window
    const windowStart = now - this.config.failureWindowMs;
    this.failures = this.failures.filter(t => t >= windowStart);
  }

  private shouldOpen(): boolean {
    return this.failures.length >= this.config.failureThreshold;
  }

  private shouldAttemptProbe(): boolean {
    return Date.now() - this.lastOpenedAt >= this.config.openDurationMs;
  }

  private remainingOpenTime(): number {
    return Math.max(0, this.config.openDurationMs - (Date.now() - this.lastOpenedAt));
  }

  private transitionTo(newState: CircuitState): void {
    const oldState = this.state;
    this.state = newState;

    if (newState === 'OPEN') {
      this.lastOpenedAt = Date.now();
      this.halfOpenSuccesses = 0;
      this.halfOpenFailures = 0;
    }
    if (newState === 'CLOSED') {
      this.failures = [];
      this.halfOpenSuccesses = 0;
      this.halfOpenFailures = 0;
    }

    console.log(`[circuit:${this.name}] ${oldState} → ${newState}`);
  }

  getState(): CircuitState {
    return this.state;
  }
}

export class CircuitOpenError extends Error {
  constructor(
    public circuitName: string,
    public retryAfterMs: number
  ) {
    super(`Circuit '${circuitName}' is OPEN. Retry after ${retryAfterMs}ms.`);
    this.name = 'CircuitOpenError';
  }
}
```

Now wrap the payment client:

```typescript
// src/services/resilient-payment-client.ts

import { CircuitBreaker } from '../resilience/circuit-breaker';
import { chargePayment, PaymentResult } from './payment-client';

const paymentCircuit = new CircuitBreaker('payment-service', {
  failureThreshold: 5,       // 5 failures...
  failureWindowMs: 10_000,   // ...in 10 seconds → open
  openDurationMs: 30_000,    // stay open for 30 seconds
  halfOpenMaxProbes: 3,      // 3 successful probes to close
});

export async function chargePaymentWithCircuitBreaker(
  orderId: string,
  amountInCents: number
): Promise<PaymentResult> {
  return paymentCircuit.call(() => chargePayment(orderId, amountInCents));
}

export function getPaymentCircuitState() {
  return paymentCircuit.getState();
}
```

---

> **Before you continue:** After 5 consecutive failures, the circuit opens. How long will requests take when the circuit is open compared to when it was closed and failing? What is the benefit of fast failure?

## 2. Try It: Watch the Circuit Open (5 minutes)

Write a test script that hammers the payment service and watches the circuit state change:

```typescript
// test/circuit-breaker-demo.ts

import { chargePaymentWithCircuitBreaker, getPaymentCircuitState } from '../src/services/resilient-payment-client';

async function demo() {
  console.log('\n=== Circuit Breaker Demo ===\n');

  for (let i = 1; i <= 20; i++) {
    const start = Date.now();
    try {
      const result = await chargePaymentWithCircuitBreaker(`ord_${i}`, 5000);
      const elapsed = Date.now() - start;
      console.log(`Request ${i}: SUCCESS (${elapsed}ms) [circuit: ${getPaymentCircuitState()}]`);
    } catch (error: any) {
      const elapsed = Date.now() - start;
      console.log(`Request ${i}: FAILED - ${error.message} (${elapsed}ms) [circuit: ${getPaymentCircuitState()}]`);
    }
    await new Promise(r => setTimeout(r, 200));
  }
}

demo();
```

Run it with the payment service in error mode:

```bash
# Terminal 1: mock payment server (already running)
# Terminal 2: set it to error mode
curl -X POST http://localhost:3001/admin/failure-mode \
  -H 'Content-Type: application/json' -d '{"mode":"error"}'

# Terminal 3: run the demo
npx ts-node test/circuit-breaker-demo.ts
```

**What you should see:**

```
Request 1: FAILED - Request failed with status 500 (45ms) [circuit: CLOSED]
Request 2: FAILED - Request failed with status 500 (38ms) [circuit: CLOSED]
Request 3: FAILED - Request failed with status 500 (41ms) [circuit: CLOSED]
Request 4: FAILED - Request failed with status 500 (39ms) [circuit: CLOSED]
Request 5: FAILED - Request failed with status 500 (42ms) [circuit: OPEN]
Request 6: FAILED - Circuit 'payment-service' is OPEN. Retry after 29800ms. (0ms) [circuit: OPEN]
Request 7: FAILED - Circuit 'payment-service' is OPEN. Retry after 29600ms. (0ms) [circuit: OPEN]
...
```

Requests 1-5 hit the failing service and each takes ~40ms. After the 5th failure, the circuit opens. Requests 6+ fail instantly (0ms) -- they never reach the payment service.

This is the key insight: **fail fast instead of fail slow**. A 0ms failure is infinitely better than a 30-second timeout.

Now heal the payment service and watch the circuit recover:

```bash
curl -X POST http://localhost:3001/admin/failure-mode \
  -H 'Content-Type: application/json' -d '{"mode":"healthy"}'
```

After 30 seconds, the circuit transitions to HALF_OPEN, sends probe requests, and if they succeed, returns to CLOSED.

---

## 3. Build: Fallback Queue (10 minutes)

<details>
<summary>💡 Hint 1: CircuitOpenError Detection</summary>
When the circuit is open, your code throws a <code>CircuitOpenError</code>. Catch this specifically with <code>if (error instanceof CircuitOpenError)</code> and route to the fallback queue instead of returning an error to the user. Other errors (network timeouts, 400s) should propagate normally.
</details>

<details>
<summary>💡 Hint 2: Queue Processing</summary>
Process the fallback queue when the circuit transitions back to CLOSED. Use a max retry count (3 attempts) per queued item. Items that fail all retries go to a dead letter queue -- log them, alert ops, and handle them manually. Never silently drop failed payments.
</details>

<details>
<summary>💡 Hint 3: User Experience</summary>
When a payment is queued (not processed immediately), return a "pending" status to the user: "Your order is confirmed -- payment processing may take a few minutes." This is a product decision, not just engineering. Discuss with your team what TicketPulse shows the user and how to handle queued payments that eventually fail.
</details>

Failing fast is better than failing slow, but failing is still bad. When the payment circuit is open, instead of telling the user "sorry, try again later," queue the purchase for processing when the service recovers.

```typescript
// src/resilience/fallback-queue.ts

interface QueuedPayment {
  orderId: string;
  amountInCents: number;
  queuedAt: Date;
  attempts: number;
}

export class PaymentFallbackQueue {
  private queue: QueuedPayment[] = [];
  private processing = false;

  enqueue(orderId: string, amountInCents: number): void {
    this.queue.push({
      orderId,
      amountInCents,
      queuedAt: new Date(),
      attempts: 0,
    });
    console.log(`[fallback-queue] Queued payment for order ${orderId} (queue size: ${this.queue.length})`);
  }

  // Process the queue when the circuit closes
  async processQueue(
    chargeFn: (orderId: string, amount: number) => Promise<any>
  ): Promise<{ processed: number; failed: number }> {
    if (this.processing) return { processed: 0, failed: 0 };
    this.processing = true;

    let processed = 0;
    let failed = 0;

    while (this.queue.length > 0) {
      const item = this.queue[0];
      try {
        await chargeFn(item.orderId, item.amountInCents);
        this.queue.shift();
        processed++;
        console.log(`[fallback-queue] Processed payment for order ${item.orderId}`);
      } catch (error) {
        item.attempts++;
        if (item.attempts >= 3) {
          this.queue.shift();
          failed++;
          console.log(`[fallback-queue] Permanently failed: order ${item.orderId} after ${item.attempts} attempts`);
          // In production: send to dead letter queue, alert ops team
        } else {
          break; // Stop processing -- service might be failing again
        }
      }
    }

    this.processing = false;
    return { processed, failed };
  }

  getQueueSize(): number {
    return this.queue.length;
  }
}
```

Update the payment client to use the fallback:

```typescript
// src/services/resilient-payment-client.ts (updated)

import { CircuitBreaker, CircuitOpenError } from '../resilience/circuit-breaker';
import { PaymentFallbackQueue } from '../resilience/fallback-queue';
import { chargePayment, PaymentResult } from './payment-client';

const paymentCircuit = new CircuitBreaker('payment-service', {
  failureThreshold: 5,
  failureWindowMs: 10_000,
  openDurationMs: 30_000,
  halfOpenMaxProbes: 3,
});

const fallbackQueue = new PaymentFallbackQueue();

export async function chargePaymentResilient(
  orderId: string,
  amountInCents: number
): Promise<{ immediate: boolean; paymentId?: string }> {
  try {
    const result = await paymentCircuit.call(() =>
      chargePayment(orderId, amountInCents)
    );
    return { immediate: true, paymentId: result.paymentId };
  } catch (error) {
    if (error instanceof CircuitOpenError) {
      // Circuit is open -- queue for later
      fallbackQueue.enqueue(orderId, amountInCents);
      return { immediate: false };
    }
    throw error; // Other errors propagate
  }
}
```

Now when the circuit is open, users see "Your order is confirmed -- payment processing may take a few minutes" instead of an error page.

> **Reflect:** This changes the user experience fundamentally. The order is "pending" instead of "confirmed." What does TicketPulse show the user? How does it handle the case where the queued payment eventually fails? These are product decisions, not just engineering decisions. Discuss with your team.

---

## 4. Retry with Exponential Backoff (10 minutes)

Before the circuit opens, individual requests should retry transient failures. But naive retries (immediate, fixed interval) can make things worse -- they amplify load on an already struggling service.

```typescript
// src/resilience/retry.ts

interface RetryConfig {
  maxRetries: number;
  baseDelayMs: number;
  maxDelayMs: number;
  jitter: boolean;  // Add randomness to prevent thundering herd
}

export async function withRetry<T>(
  fn: () => Promise<T>,
  config: RetryConfig
): Promise<T> {
  let lastError: Error | undefined;

  for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error: any) {
      lastError = error;

      if (attempt === config.maxRetries) break;

      // --- YOUR DECISION POINT ---
      // Should all errors be retried? No.
      // - 500, 502, 503, 504: yes (transient server errors)
      // - 429: yes, but respect Retry-After header
      // - 400, 401, 403, 404: no (client errors, retrying won't help)
      // - Network timeout: yes (transient)
      //
      // Implement your own isRetryable() function.

      if (!isRetryable(error)) throw error;

      const delay = calculateBackoff(attempt, config);
      console.log(`[retry] Attempt ${attempt + 1} failed, retrying in ${delay}ms...`);
      await new Promise(r => setTimeout(r, delay));
    }
  }

  throw lastError;
}

function calculateBackoff(attempt: number, config: RetryConfig): number {
  // Exponential: 100ms → 200ms → 400ms → 800ms → ...
  let delay = config.baseDelayMs * Math.pow(2, attempt);
  delay = Math.min(delay, config.maxDelayMs);

  if (config.jitter) {
    // Full jitter: random between 0 and calculated delay
    // This prevents all retrying clients from hitting the service at the same instant
    delay = Math.random() * delay;
  }

  return Math.floor(delay);
}

function isRetryable(error: any): boolean {
  if (error.response) {
    const status = error.response.status;
    return status >= 500 || status === 429;
  }
  // Network errors (ECONNREFUSED, ETIMEDOUT) are retryable
  if (error.code === 'ECONNREFUSED' || error.code === 'ETIMEDOUT') {
    return true;
  }
  return false;
}
```

Why jitter matters:

```
WITHOUT jitter (thundering herd):
  Client A retries at: 100ms, 200ms, 400ms
  Client B retries at: 100ms, 200ms, 400ms
  Client C retries at: 100ms, 200ms, 400ms
  → 3 requests hit the server simultaneously at each interval

WITH full jitter:
  Client A retries at: 73ms, 156ms, 312ms
  Client B retries at: 42ms, 189ms, 267ms
  Client C retries at: 91ms, 104ms, 389ms
  → Requests are spread out, giving the server breathing room
```

---

## 5. Bulkhead Isolation (8 minutes)

Even with circuit breakers, a slow payment service can exhaust the order service's resources (connections, threads, memory). Bulkheads limit how much of your capacity any single dependency can consume.

The name comes from ships: bulkheads are walls between compartments. If one compartment floods, the others stay dry.

```typescript
// src/resilience/bulkhead.ts

export class Bulkhead {
  private active: number = 0;
  private queue: Array<{ resolve: () => void; reject: (err: Error) => void }> = [];

  constructor(
    private name: string,
    private maxConcurrent: number,
    private maxQueueSize: number
  ) {}

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.active >= this.maxConcurrent) {
      if (this.queue.length >= this.maxQueueSize) {
        throw new BulkheadFullError(this.name, this.active, this.queue.length);
      }

      // Wait in the queue
      await new Promise<void>((resolve, reject) => {
        this.queue.push({ resolve, reject });
      });
    }

    this.active++;
    try {
      return await fn();
    } finally {
      this.active--;
      // Let the next queued request through
      if (this.queue.length > 0) {
        const next = this.queue.shift()!;
        next.resolve();
      }
    }
  }

  getStats() {
    return {
      active: this.active,
      queued: this.queue.length,
      maxConcurrent: this.maxConcurrent,
    };
  }
}

export class BulkheadFullError extends Error {
  constructor(name: string, active: number, queued: number) {
    super(`Bulkhead '${name}' is full: ${active} active, ${queued} queued`);
    this.name = 'BulkheadFullError';
  }
}
```

Apply it:

```typescript
// src/services/resilient-payment-client.ts (final version)

// Payment service gets at most 10 concurrent connections from this service
// Other services (event listing, search, user profile) are unaffected
const paymentBulkhead = new Bulkhead('payment', 10, 20);

export async function chargePaymentResilient(
  orderId: string,
  amountInCents: number
): Promise<{ immediate: boolean; paymentId?: string }> {
  try {
    const result = await paymentBulkhead.execute(() =>
      paymentCircuit.call(() =>
        withRetry(
          () => chargePayment(orderId, amountInCents),
          { maxRetries: 2, baseDelayMs: 100, maxDelayMs: 1000, jitter: true }
        )
      )
    );
    return { immediate: true, paymentId: result.paymentId };
  } catch (error) {
    if (error instanceof CircuitOpenError || error instanceof BulkheadFullError) {
      fallbackQueue.enqueue(orderId, amountInCents);
      return { immediate: false };
    }
    throw error;
  }
}
```

Notice the layering order: **bulkhead** (limits concurrency) wraps **circuit breaker** (stops calling a dead service) wraps **retry** (handles transient failures). Each layer addresses a different failure mode.

---

## 6. Timeout Strategy (4 minutes)

Every outbound call gets a timeout. No exceptions.

```typescript
// src/services/payment-client.ts (updated)

import axios from 'axios';

const PAYMENT_SERVICE_URL = process.env.PAYMENT_SERVICE_URL || 'http://payment-service:3001';

export async function chargePayment(
  orderId: string,
  amountInCents: number
): Promise<PaymentResult> {
  const response = await axios.post(
    `${PAYMENT_SERVICE_URL}/charge`,
    { orderId, amountInCents },
    {
      timeout: 5000,  // 5 seconds -- hard limit
      // Connect timeout is separate from response timeout in some clients
    }
  );
  return response.data;
}
```

> **Reflect:** What is the right timeout for a payment call?
>
> - Too short (500ms): Legitimate requests fail when the network is slow. You get false positives.
> - Too long (30s): A slow service ties up your resources for 30 seconds per request. 100 concurrent requests = 100 threads stuck for 30 seconds.
> - Reasonable starting point: p99 latency of the healthy service * 2. If the payment service normally responds in 200ms at p99, set the timeout to 400-500ms.
>
> Measure first. Your tracing data from L2-M41 tells you the real latency distribution.

---

## 7. Observe: Metrics (5 minutes)

Expose circuit breaker state as Prometheus metrics so you can see it in Grafana:

```typescript
// src/resilience/circuit-breaker-metrics.ts

import { Registry, Gauge, Counter } from 'prom-client';

export function instrumentCircuitBreaker(breaker: CircuitBreaker, registry: Registry) {
  const stateGauge = new Gauge({
    name: 'circuit_breaker_state',
    help: 'Circuit breaker state: 0=closed, 1=open, 2=half_open',
    labelNames: ['circuit'],
    registers: [registry],
  });

  const failureCounter = new Counter({
    name: 'circuit_breaker_failures_total',
    help: 'Total failures recorded by circuit breaker',
    labelNames: ['circuit'],
    registers: [registry],
  });

  const shortCircuitCounter = new Counter({
    name: 'circuit_breaker_short_circuits_total',
    help: 'Requests short-circuited by open circuit',
    labelNames: ['circuit'],
    registers: [registry],
  });

  // Poll state periodically
  setInterval(() => {
    const state = breaker.getState();
    const stateValue = state === 'CLOSED' ? 0 : state === 'OPEN' ? 1 : 2;
    stateGauge.set({ circuit: breaker['name'] }, stateValue);
  }, 1000);
}
```

Create a Grafana dashboard panel:

```
Circuit Breaker State Over Time:
  Query: circuit_breaker_state{circuit="payment-service"}
  Legend: {{circuit}}
  Thresholds: 0 (green/closed), 1 (red/open), 2 (yellow/half-open)

Short-Circuited Requests Rate:
  Query: rate(circuit_breaker_short_circuits_total[1m])
  Alert: if > 0 for 1 minute → page the on-call engineer
```

---

## Checkpoint

Before continuing, verify:

- [ ] Circuit breaker transitions through CLOSED → OPEN → HALF_OPEN → CLOSED
- [ ] Open circuit fails requests in <1ms (no network call)
- [ ] Fallback queue captures requests during circuit-open periods
- [ ] Retries use exponential backoff with jitter
- [ ] Bulkhead limits concurrent requests to the payment service
- [ ] Every outbound call has a timeout

```bash
git add -A && git commit -m "feat: add circuit breaker, retry, bulkhead, and fallback for payment service"
```

---

## Reflect

> **What did you notice?** When the circuit breaker opened and requests started failing in 0ms instead of waiting for a timeout, how significant was the difference? Did the fallback queue change how you think about user experience during partial outages?

**The resilience stack in order of importance:**

1. **Timeouts** -- the most basic and most important. Without timeouts, everything else is moot.
2. **Retries with backoff** -- handles transient failures without manual intervention.
3. **Circuit breakers** -- prevents cascading failures when a dependency is consistently failing.
4. **Bulkheads** -- limits blast radius so one failing dependency does not consume all resources.
5. **Fallbacks** -- degrades gracefully instead of failing completely.

**The meta-lesson:** Resilience is about accepting that failures will happen and designing for them. A system that never fails is impossible. A system that fails gracefully is achievable.

---

## Key Terms

| Term | Definition |
|------|-----------|
| **Circuit breaker** | A stability pattern that stops calling a failing service after a threshold, allowing it time to recover. |
| **Bulkhead** | A resilience pattern that isolates components so a failure in one does not cascade to others. |
| **Retry** | Automatically re-attempting a failed operation, typically with increasing delays between attempts. |
| **Backoff** | A strategy of progressively increasing the wait time between retry attempts to reduce load on a failing system. |
| **Jitter** | Random variation added to backoff intervals to prevent many clients from retrying simultaneously. |
| **Timeout** | A maximum duration allowed for an operation to complete before it is aborted and treated as a failure. |

---

## What's Next

In **Rate Limiting** (L2-M50), you'll protect TicketPulse's APIs from abuse and overload with token buckets, sliding windows, and distributed rate limiting.

---

## Further Reading

- Michael Nygard, "Release It!" -- the book that introduced the circuit breaker pattern to software
- Netflix Hystrix -- the library that popularized these patterns (now in maintenance mode; see resilience4j for JVM)
- AWS Builders Library, "Timeouts, retries, and backoff with jitter" -- practical guidance from Amazon's engineering team
